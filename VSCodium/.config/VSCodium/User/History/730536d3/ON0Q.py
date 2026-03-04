from __future__ import annotations

from fastapi.requests import HTTPConnection
import json
import logging
import string
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from secrets import token_hex
from typing import TYPE_CHECKING, Any, Optional, Union
from urllib.parse import urljoin
from uuid import UUID

import httpx
from email_validator import EmailNotValidError
from email_validator import validate_email as email_validator_function
from fastapi import Request
from fastapi_babel import _
from python_usernames import is_safe_username
from python_usernames.reserved_words import get_reserved_words
from starlette.routing import NoMatchFound
from werkzeug.datastructures import LanguageAccept

from ..core.ecdsa_lib import sign_data, verify_signature
from .database.async_manager import AsyncDatabaseAdapter
from ..core.exceptions import Auth54ValidationError
from ..core.utils import (
    create_response_message,
    generate_random_string,
    is_valid_public_key,
    json_dumps,
    print_error_cli,
)
from .exceptions import AuthServiceNotRegistered, Forbidden, Unauthorized

if TYPE_CHECKING:
    from .actor import Actor

if TYPE_CHECKING:
    from .actor import Actor


KEY_CHARS = string.ascii_lowercase + string.ascii_uppercase + string.digits

# Urls on apps in google market and appstore
ERP_APP_URL = dict(
    android="https://play.google.com/store/apps/details?id=ecosystem54.android",
    ios="https://apps.apple.com/us/app/ecosystem54/id1496286184",
)


def get_session_token(request: HTTPConnection):
    """
    Get session token from request.
    :return: session_token or None in case if session_token is not present in cookies or request
    @subm_flow
    """
    session_token = None
    # FIXME: Receiving sesion_token from cookies is TEMPORARY, because for some reason,
    # endpoints cant access it from session cookie from SessionMiddleware
    if "Session-Token" in request.headers or "session_token" in request.session or request.cookies.get('session_token'):
        session_token = request.headers.get("Session-Token")
        if not session_token:
            session_token = request.session.get("session_token")
            if not session_token:
                session_token = request.cookies.get("session_token")

    return session_token


async def get_session(db: AsyncDatabaseAdapter, session_token: str):
    """
    Get session by session_token
    :param session_token: token of the session
    :return: session object if exists
    """
    service_session_token = await db.fetchone(
        """SELECT * FROM service_session_token WHERE session_token=$1""", session_token
    )

    return service_session_token


def validate_email(request: HTTPConnection, email: str) -> None:
    """
    Validate passed email value.
    @subm_flow
    """
    try:
        email_validator_function(email)
    except EmailNotValidError as e:
        logging_message(request, str(e))
        raise Auth54ValidationError("Invalid email")


def validate_login(request: HTTPConnection, login_value: str):
    """
    Validate passed login value.
    @subm_flow
    """
    banned_words = request.app.config.get("BANNED_WORDS_FOR_LOGIN", [])
    if banned_words:
        if isinstance(banned_words, str):
            banned_words = banned_words.splitlines()
        else:
            try:
                iter(banned_words)
            except TypeError:
                banned_words = []
    if len(login_value) >= 3 and is_safe_username(
        login_value,
        whitelist=get_reserved_words(),
        blacklist=banned_words,
        max_length=36,
    ):
        return True
    return False


def logging_message(
    request: HTTPConnection,
    message: str,
    level: str = "error",
    status: int = 400,
    logger_name: str = "auth_submodule",
) -> None:
    """
    Depends by settings write log file/print in concole message

    params:
        message: string to output in console/log
        level: log level, default 'error'
        status: if console and level 'error' provide status to func
        logger_name: Logging name if use not in submodule must be provide
        app: Flask or FastAPI app instance
    """
    if not request.app.config.get("ECOSYSTEM54_LOGGING_MODULE_ENABLED"):
        if level == "error":
            print_error_cli(message, status)
        else:
            print(message)
    else:
        try:
            logger = logging.getLogger(logger_name)
            method = getattr(logger, level)
            method(message)
        except AttributeError:
            logger.error(message)


def is_valid_uuid(request: HTTPConnection, uuid: str, version: Optional[int] = None):
    """
    Check if uuid is valid UUID
    :param uuid: string uuid on test
    :param version: uuid version
    :return: True if valid else False
    @subm_flow
    """
    if not isinstance(uuid, str):
        try:
            uuid = str(uuid)
        except Exception:
            logging_message(request, "Error while converting uuid in string")
            return False

    if version:
        try:
            uuid_obj = UUID(uuid, version=version)
        except (AttributeError, ValueError, TypeError):
            return False

        return str(uuid_obj) == uuid

    check_result = None
    for version in range(1, 6):
        try:
            uuid_obj = UUID(uuid, version=version)
        except (AttributeError, ValueError, TypeError):
            continue

        check_result = str(uuid_obj) == uuid
        if not check_result:
            continue
        else:
            return check_result

    return check_result


async def get_current_actor(
    db: AsyncDatabaseAdapter, request: HTTPConnection, raise_exception=True
) -> Optional[Actor]:
    """
    Get current actor from g or by session token or raise Unauthorized
    :param raise_exception: bool. Should service raise Unauthorized if there is no such actor.
    :return: actor or None or raise exception
    """
    from .actor import Actor, ActorNotFound

    session_token = get_session_token(request)
    if not session_token and not raise_exception:
        return None

    try:
        actor = await Actor.objects.get_by_session(
            request, db, session_token=session_token
        )
        return actor
    except ActorNotFound:
        if not raise_exception:
            return None

    raise Unauthorized


async def get_default_user_group(db: AsyncDatabaseAdapter, request: HTTPConnection):
    """
    Get default user group. By default user adds in this group
    :return: group
    @subm_flow
    """
    group = await db.fetchone(
        """SELECT * FROM actor WHERE actor_type='group' AND uinfo->>'group_name'=$1""",
        request.app.config.get("DEFAULT_GROUP_NAME", "DEFAULT"),
    )
    return group


def check_if_auth_service(request: HTTPConnection):
    """
    Checks if service auth or not.
    :return: boolean value. True - if service auth, False - if not
    @subm_flow Checks if service auth or not
    """
    salt = token_hex(16)
    signature = sign_data(request.app.config["SERVICE_PRIVATE_KEY"], salt)
    if request.app.config.get("AUTH_STANDALONE"):
        if not verify_signature(
            request.app.config["SERVICE_PUBLIC_KEY"], signature, salt
        ):
            return False
    else:
        if not verify_signature(request.app.config["AUTH_PUB_KEY"], signature, salt):
            return False
    return True


def get_language_header(request: Request) -> dict[str, str]:
    """
    Create custom header with setting locale for requests on other services and receiving messages in set language
    :return: dict
    """
    return {"Http-Accept-Language": get_service_locale(request)}


def get_service_locale(request: Request) -> str:
    """
    Get locale code that service is using for this user by request.
    :return: string
    """
    try:
        locale = request.state.babel.locale
    except TypeError as e:
        logging_message(request, "Error with getting locale - %s" % str(e))
        locale = request.cookies.get(
            request.app.config.get("LANGUAGE_COOKIE_KEY", None)
        )
        if not locale or locale not in request.app.config.get(
            "LANGUAGES", ["en", "ru"]
        ):
            accept_languages = parseAcceptLanguage(
                request.headers.get("Accept-Language", "")
            )
            locale = LanguageAccept(accept_languages).best_match(
                request.app.config.get("LANGUAGES", ["en", "ru"])
            )
    except Exception as e:
        logging_message(request, "Exception with getting locale - %s" % str(e))
        locale = "en"

    return str(locale) if locale else "en"


def parseAcceptLanguage(acceptLanguage):
    """Parse Accept-Language request header into a list of tuples (lang, weight)"""

    languages = acceptLanguage.split(",")
    locale_q_pairs = []

    for language in languages:
        if language.split(";")[0] == language:
            # no q => q = 1
            locale_q_pairs.append((language.strip(), 1))
        else:
            locale = language.split(";")[0].strip()
            q = language.split(";")[1].split("=")[1]
            locale_q_pairs.append((locale, float(q)))

    return locale_q_pairs


async def get_auth_domain(
    db: AsyncDatabaseAdapter, request: Request, internal: bool = False
) -> str:
    """
    Get auth domain from database using AUTH PUBLIC KEY.
    :return: string
    """
    query = """SELECT
                uinfo->>'service_domain' AS service_domain,
                uinfo->>'internal_service_domain' AS internal_service_domain
                FROM actor WHERE initial_key = $1"""
    if request.app.config.get("AUTH_STANDALONE"):
        values = request.app.config["SERVICE_PUBLIC_KEY"]
    else:
        values = request.app.config["AUTH_PUB_KEY"]

    domain = await db.fetchone(query, values)
    if not domain:
        raise AuthServiceNotRegistered

    if internal and request.app.config.get("INTERNAL_DOMAINS_ENABLED", True):
        result = domain.get("internal_service_domain") or domain.get("service_domain")
    else:
        result = domain.get("service_domain")

    if not result:
        raise AuthServiceNotRegistered

    return result


async def get_static_group(db: AsyncDatabaseAdapter, group_name: str):
    """
    Get BAN or ADMIN or DEFAULT group.
    :param group_name: group name (BAN or ADMIN or DEFAULT)
    :return: group_uuid
    """
    group = await db.fetchone(
        """SELECT uuid FROM actor WHERE actor_type='group' AND uinfo->>'group_name'=$1""",
        group_name,
    )
    return group


async def get_service_certificate(
    request: Request, db: AsyncDatabaseAdapter, service_uuid: str, domain: str
) -> Union[bool, str]:
    result = True
    certificate = await db.fetchone(
        """SELECT certificate as certificate
        FROM certificate WHERE service_uuid = $1 AND domain = $2
        ORDER BY created DESC LIMIT 1;
        """,
        service_uuid,
        domain,
    )
    certificate = certificate.get("certificate") if certificate else None

    if certificate:
        result = f"/tmp/{service_uuid}"
        try:
            with open(result, "w") as file:
                file.write(certificate)
        except Exception as e:
            logging_message(
                request, f"Error with writing certificate to tmp directory \n {e}"
            )

    return result


async def actor_exists(db: AsyncDatabaseAdapter, uuid: str):
    """
    Check if user exists on service
    :param uuid: user uuid we need to check
    :return: True if exists, False if not
    @subm_flow_sudm
    """
    # Check if user exists on service
    result = await db.fetchone(
        """SELECT EXISTS(SELECT 1 FROM actor WHERE uuid=$1)""", uuid
    )
    if result and result.get("exists"):
        return True

    return False


async def create_actor(request: Request, db: AsyncDatabaseAdapter, apt54: dict):
    """
    Create actor on client service
    :param apt54: user apt54
    :return: actor if created or None if not
    @subm_flow_sudm
    """
    data = apt54["user_data"]
    query = """INSERT INTO actor SELECT * FROM jsonb_populate_record(null::actor, $1::jsonb) RETURNING uuid"""
    values = data
    try:
        actor_uuid = await db.fetchone(query, values)
        query = """SELECT * FROM actor WHERE uuid = $1"""
        values = actor_uuid.get("uuid") if actor_uuid else None
        actor = await db.fetchone(query, values) if values else None
    except Exception as e:
        logging_message(request, "Exception on creating actor! %s" % e)
        actor = None

    return actor


async def create_masquerading_session_token(
    request: Request,
    db: AsyncDatabaseAdapter,
    actor_uuid: str,
    expiration_days: int = 1,
    expiration_hours: int = 0,
    expiration_minutes: int = 0,
    token_type: str = "masquerading",
):
    from .actor import Actor, ActorNotFound

    if not actor_uuid or not is_valid_uuid(request, actor_uuid):
        raise ValueError("Invalid actor uuid was sent")

    try:
        actor = await Actor.objects.get(request=request, db=db, uuid=actor_uuid)
    except ActorNotFound as e:
        if request.app.config.get("AUTH_STANDALONE") or check_if_auth_service(request):
            raise e
        from .service_view import GetAndUpdateActor

        response = await GetAndUpdateActor(request, db, uuid=actor_uuid).update_actor()
        if not response.is_success:
            raise e

        try:
            actor = await Actor.objects.get(request, db, uuid=actor_uuid)
        except ActorNotFound:
            raise e

    if actor.actor_type not in ("user", "classic_user"):
        raise ValueError("Invalid actor type")

    current_actor = await get_current_actor(db=db, request=request)

    if not current_actor:
        raise Forbidden("Current actor not found")

    if actor.is_root(request):
        logging_message(
            request,
            message=f"Actor <{current_actor.uuid}> tried to masquerade root actor <{actor.uuid}>",
            status=403,
        )
        raise Forbidden("Permissions denied")
    elif await actor.is_admin(request, db) and not (
        await current_actor.is_admin(request, db) or current_actor.is_root(request)
    ):
        logging_message(
            request,
            message=f"Non-admin actor <{current_actor.uuid}> tried to masquerade admin actor <{actor.uuid}>",
            status=403,
        )
        raise Forbidden("Permissions denied")

    session_token = generate_random_string()
    expiration = datetime.strftime(
        datetime.now(timezone.utc)
        + timedelta(
            days=expiration_days, hours=expiration_hours, minutes=expiration_minutes
        ),
        "%Y-%m-%d %H:%M:%S",
    )
    masquerading_apt54 = {
        "expiration": expiration,
        "masquerade_performer_uuid": current_actor.uuid,
        "user_data": actor.to_dict(),
    }

    await db.execute(
        """INSERT INTO service_session_token(session_token, uuid, apt54, service_uuid, token_type)
            VALUES ($1, $2, $3, $4, $5)""",
        session_token,
        actor_uuid,
        masquerading_apt54,
        request.app.config.get("SERVICE_UUID"),
        token_type,
    )

    return session_token


async def create_new_salt(
    request: Request,
    db: AsyncDatabaseAdapter,
    user_info: dict,
    salt_for: Optional[str] = None,
):
    """
    Generates a random salt and save it in database with uuid or public_key
    :param user_info: dictionary with key uuid or pub_key
    :param salt_for: string with argument what for we creating salt
    :return: salt: random generated hex string
    @subm_flow Generates a random salt and save it in database with uuid or public_key
    """
    salt = token_hex(16)

    if user_info.get("pub_key"):
        pub_key = user_info["pub_key"]
        if not is_valid_public_key(pub_key):
            return None
        await db.execute(
            "INSERT INTO salt_temp(salt, pub_key, salt_for) VALUES ($1, $2, $3)",
            salt,
            user_info.get("pub_key"),
            salt_for,
        )
    elif user_info.get("uuid"):
        user_uuid = user_info["uuid"]
        if not is_valid_uuid(request, user_uuid):
            return None

        result = await db.fetchone(
            """SELECT EXISTS(SELECT 1 FROM actor WHERE uuid = $1)""",
            user_info.get("uuid"),
        )
        if result:
            exists = result.get("exists")
            if not exists:
                # local import only
                from .service_view import GetAndUpdateActor

                response = await GetAndUpdateActor(
                    request, db, uuid=user_uuid
                ).update_actor()
                if not response.is_success:
                    return None

            await db.execute(
                "INSERT INTO salt_temp(salt, uuid, salt_for) VALUES ($1, $2::uuid, $3)",
                salt,
                user_info.get("uuid"),
                salt_for,
            )
    elif user_info.get("qr_token", None):
        await db.execute(
            "INSERT INTO salt_temp(salt, qr_token, salt_for) VALUES ($1, $2, $3)",
            salt,
            user_info.get("qr_token"),
            salt_for,
        )
    else:
        return None

    return salt


async def create_session(
    db: AsyncDatabaseAdapter,
    request: Request,
    user_data: dict,
    auxiliary_token: str = "",
    service_uuid: str = "",
    depended_info: dict = {},
):
    """
    Session generation on service based on user_data
    :param user_data: dict. User's signature
    :param auxiliary_token: string value of generate salt
    :param service_uuid: target service uuid fir what session_token is creating
    :param depended_info: data for creation session on depended_services
    :return: session_token: str. Service session token
    @subm_flow Session generation on service based on user data
    """
    from .actor import Actor

    actor = Actor(request, user_data)
    if is_banned_result := await check_actor_is_banned(db, request, actor):
        return is_banned_result

    expiration_period = get_custom_session_expiration_period(request)
    if not expiration_period:
        expiration_period = timedelta(days=14)
    expiration = datetime.strftime(
        datetime.now(timezone.utc) + expiration_period, "%Y-%m-%d %H:%M:%S"
    )
    # TODO add signature with service private key?
    apt54 = {"user_data": user_data, "expiration": expiration}

    if not actor.uuid:
        raise Auth54ValidationError("Actor UUID is missing")

    result = await create_session_token(
        db=db,
        request=request,
        uuid=actor.uuid,
        apt54=apt54,
        auxiliary_token=auxiliary_token,
        service_uuid=service_uuid,
        depended_info=depended_info,
    )

    if (
        result
        and request.app.config.get("SESSION_STORAGE", None) == "SESSION"
        or request.app.config.get("SESSION_STORAGE") is None
    ):
        request.session["session_token"] = result.get("session_token")

    result["expiration"] = expiration
    return result


async def check_actor_is_banned(
    db: AsyncDatabaseAdapter, request: Request, actor: Actor
):
    if await actor.is_banned(db) and not actor.is_root(request):
        response = create_response_message(
            message=_(
                "You are in ban group. "
                "Please contact the administrator to set you role."
            ),
            error=True,
        )
        return response


def get_custom_session_expiration_period(
    request: Request, period=None, as_timedelta=True
):
    session_token_lifetime = (
        request.app.config.get("SESSION_TOKEN_LIFETIME_DAYS")
        if period is None
        else period
    )
    if session_token_lifetime:
        try:
            custom_expiration_period = timedelta(days=session_token_lifetime)
        except Exception:
            logging_message(
                request,
                f"""Invalid value for SESSION_TOKEN_LIFETIME_DAYS - {session_token_lifetime},
                type - {type(session_token_lifetime)}. Default value was applied""",
            )
        else:
            return custom_expiration_period if as_timedelta else session_token_lifetime


async def create_session_token(
    db: AsyncDatabaseAdapter,
    request: Request,
    uuid: str,
    apt54: dict,
    auxiliary_token: Optional[str] = None,
    service_uuid: Optional[str] = None,
    depended_info: dict = {},
) -> dict:
    while True:
        result = dict(session_token=generate_random_string(KEY_CHARS))

        query_result = await db.fetchone(
            """SELECT EXISTS(SELECT 1 FROM service_session_token WHERE session_token=$1)""",
            result.get("session_token"),
        )
        if query_result:
            if query_result.get("exists"):
                continue

        await db.execute(
            """INSERT INTO service_session_token(session_token, uuid, apt54, auxiliary_token, service_uuid)
                VALUES ($1, $2, $3, $4, $5)""",
            result.get("session_token"),
            uuid,
            apt54,
            auxiliary_token,
            service_uuid or request.app.config["SERVICE_UUID"],
        )

        if depended_info:
            await make_session_in_depended_services(
                depended_info, result, request=request
            )

        # FIXME: this should already be dict
        return dict(result)


async def make_session_in_depended_services(
    depended_info: dict, autentication_result: dict, request: Request
):
    """
    Send requests to depended services and get session tokens from them
    @subm_flow
    """
    depended_services_source = get_depended_services_source(
        request=request, full_source=True
    )

    async with httpx.AsyncClient() as client:
        for name, service_data in depended_info.items():
            try:
                base = depended_services_source.get(name.lower())
                url = urljoin(base, "/auth/")
                resp = await client.post(url, json=service_data)
                data = resp.json()
                autentication_result.update(
                    {f"{name}_session_token": data.get("session_token")}
                )
            except Exception:
                pass


def get_depended_services_source(request: Request, full_source=False):
    """
    Get depended services from app config
    If DYNAMIC_DEPENDED_SERVICES_ENABLED, get depended services from DYNAMIC_DEPENDED_SERVICES dict
    by HTTP_ORIGIN(front domain) as key.
    """
    dynamic_services = request.app.config.get("DYNAMIC_DEPENDED_SERVICES")
    if (
        request.app.config.get("DYNAMIC_DEPENDED_SERVICES_ENABLED")
        and dynamic_services
        and isinstance(dynamic_services, dict)
    ):
        if not full_source:
            origin = request.scope.get(
                "HTTP_ORIGIN", request.app.config.get("SERVICE_DOMAIN")
            )
            if origin in dynamic_services:
                return dynamic_services[origin]
        else:
            full_data = {}
            for source in dynamic_services.values():
                full_data.update(source)
            return full_data
    elif services := request.app.config.get("DEPENDED_SERVICES"):
        if isinstance(services, dict):
            return services

    return {}


async def create_session_with_apt54(
    apt54: dict, request: Request, db: AsyncDatabaseAdapter, auxiliary_token: str = ""
):
    """
    Session generation on service based on apt54
    :param apt54: dict. User's apt54
    :param auxiliary_token: temporary_session generated during Single-Sign-On
    :return: session_token: str. Service session token
    @subm_flow Session generation on service based on apt54
    """
    from .actor import Actor

    uuid = (
        apt54["user_data"].get("uuid") if apt54.get("user_data") else apt54.get("uuid")
    )
    actor: Actor = await Actor.objects.get(request, db, uuid=uuid)
    is_banned_result = await check_actor_is_banned(db, request, actor)
    if is_banned_result:
        return is_banned_result

    result = await create_session_token(db, request, actor.uuid, apt54, auxiliary_token)
    return result


async def create_temporary_session(
    db: AsyncDatabaseAdapter, request: Request, actor_uuid=None
):
    """
    Create temporary session. Need for saving in cookies before redirect on auth.
    :return: temporary_session
    """
    while True:
        temporary_session = generate_random_string(KEY_CHARS)

        result = await db.fetchone(
            """SELECT EXISTS(SELECT 1 FROM temporary_session WHERE temporary_session=$1)""",
            temporary_session,
        )
        if result and result.get("exists"):
            continue

        await db.execute(
            """INSERT INTO temporary_session(temporary_session, service_uuid, actor_uuid) VALUES ($1, $2, $3)""",
            temporary_session,
            request.app.config["SERVICE_UUID"],
            actor_uuid,
        )

        return temporary_session


async def delete_temporary_session(
    db: AsyncDatabaseAdapter, request: Request, temporary_session: Optional[str] = None
):
    """
    Delete temporary session from database
    :return: None
    """
    if not temporary_session:
        temporary_session = await get_temporary_session(db, request)

    await db.execute(
        "DELETE FROM temporary_session WHERE temporary_session = $1", temporary_session
    )


async def get_temporary_session(
    db: AsyncDatabaseAdapter,
    request: Request,
    temporary_session_token: Optional[str] = None,
):
    """
    Get temporary session info from database
    :return: temporary_session
    """
    temporary_session_token = temporary_session_token or get_temporary_session_token(
        request=request
    )
    if not temporary_session_token:
        return None

    temporary_session = await db.fetchone(
        """SELECT * FROM temporary_session WHERE temporary_session = $1
    ORDER BY created DESC LIMIT 1 """,
        temporary_session_token,
    )

    return temporary_session


def get_temporary_session_token(request: Request):
    """
    Get temporary session token from cookies.
    :return: temporary_session_token
    """
    return request.cookies.get("temporary_session", None)


async def get_apt54(
    request: Request,
    db: AsyncDatabaseAdapter,
    uuid: str,
):
    """
    Send POST request on auth for getting apt54
    :param uuid: user uuid
    :return: apt54 or None
    @subm_flow
    """
    if request.app.config.get("AUTH_STANDALONE"):
        result = await get_apt54_locally(request, db, uuid=uuid)
        return result

    base = await get_auth_domain(db, request, internal=True)
    url = urljoin(base, "/get_apt54/")
    data = dict(uuid=uuid, service_uuid=request.app.config["SERVICE_UUID"])

    # Request custom expiration date
    if not check_if_auth_service(request):
        expiration_period = get_custom_session_expiration_period(
            request, as_timedelta=False
        )
        if expiration_period:
            data["requested_expiration_period"] = expiration_period

    data["signature"] = sign_data(
        request.app.config["SERVICE_PRIVATE_KEY"], json_dumps(data, sort_keys=True)
    )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url, json=data, headers=get_language_header(request)
            )
    except Exception:
        logging_message(request, "Auth is unreachable", status=500)
        return None, 500

    data = response.json()
    if response.is_success:
        if verify_apt54(request, data):
            return data, response.status_code

    return data, response.status_code


def verify_apt54(request: Request, apt54: dict):
    """
    APT54 verification that user received it from auth and didn't change any data
    :param apt54: user APT54
    :return: verification result. True - verification passed, False - verification failed
    @subm_flow
    """
    signature = apt54.get("signature")
    data = apt54.get("user_data")
    user_data = json_dumps(data, sort_keys=True) if data else "{}"
    data = str(user_data) + str(apt54.get("expiration"))
    if request.app.config.get("AUTH_STANDALONE"):
        if not verify_signature(
            request.app.config["SERVICE_PUBLIC_KEY"], signature, data
        ):
            return False
    else:
        if not verify_signature(request.app.config["AUTH_PUB_KEY"], signature, data):
            return False
    return True


async def get_apt54_locally(request: Request, db: AsyncDatabaseAdapter, uuid: str):
    """
    Build apt54 locally
    :param uuid:
    :return: apt54 or None
    @subm_flow Build apt54 locally
    """
    from .actor import Actor, ActorNotFound

    try:
        actor = await Actor.objects.get(request, db, uuid=uuid)
    except ActorNotFound:
        return None, 452

    data = json_dumps(actor.to_dict(), sort_keys=True)

    expiration_period = get_custom_session_expiration_period(request)
    if not expiration_period:
        expiration_period = timedelta(days=14)

    expiration = datetime.strftime(
        datetime.now(timezone.utc) + expiration_period, "%Y-%m-%d %H:%M:%S"
    )
    signature = sign_data(request.app.config["SERVICE_PRIVATE_KEY"], data + expiration)
    response = dict(
        user_data=json.loads(data), expiration=expiration, signature=signature
    )
    return response, 200


async def get_public_key(db: AsyncDatabaseAdapter, uuid: str):
    """
    Getting user public key
    :param uuid: user uuid
    :return: initial_key, secondary keys: initial_key - primary user public key
    saved in registration process (PRIMARY), secondary_key - list of generated
    user public keys
    @subm_flow
    """
    secondary_keys = None
    data = await db.fetchone(
        "SELECT initial_key, secondary_keys FROM actor WHERE uuid=$1", uuid
    )

    if not data:
        # Such user does not exists
        return None, None
    if data.get("secondary_keys"):
        secondary_keys = data["secondary_keys"].values()

    initial_key = data.get("initial_key")
    return initial_key, secondary_keys


async def get_salt_from_depended_services(data: dict, request: Request) -> dict:
    """
    Get authentication salt from depended services (async httpx version)
    """
    depended_services_info = {}
    if depended_services_source := get_depended_services_source(request=request):
        service_data = dict(data)
        service_data["step"] = "identification"

        async with httpx.AsyncClient(timeout=5.0) as client:
            for name, domain in depended_services_source.items():
                try:
                    resp = await client.post(
                        urljoin(domain, "/auth/"), json=service_data
                    )
                except Exception as e:
                    print(f"Error contacting {domain}: {e}")
                    continue
                else:
                    if resp.status_code == 200:
                        try:
                            depended_services_info[name] = resp.json()
                        except Exception as e:
                            print(f"Invalid JSON from {domain}: {e}")
    return depended_services_info


async def get_session_token_by_auxiliary(
    db: AsyncDatabaseAdapter, auxiliary_token: Optional[str] = None
):
    """
    Get session by auxiliary_token.
    :param auxiliary_token: string. Some token which we use to save session. Example: QR token = auxiliary token.
    :return: session
    """
    service_session_token = await db.fetchone(
        """SELECT session_token FROM service_session_token
            WHERE auxiliary_token=$1""",
        auxiliary_token,
    )

    return service_session_token


async def get_user_salt(
    request: Request,
    db: AsyncDatabaseAdapter,
    user_info: dict,
    salt_for: Optional[str] = None,
):
    """
    Get salt that was sent to user to sign
    :param user_info: dictionary with key uuid or pub_key
    :param salt_for:  string with argument what for we creating salt
    :return: salt or None if not exists row
    @subm_flow Get salt that was sent to user to sign
    """

    if user_info.get("qr_token", None):
        salt = await db.fetchone(
            """SELECT salt FROM salt_temp WHERE qr_token = $1 AND uuid = $2 AND salt_for=$3 AND
                created > timezone('utc', now()) ORDER BY created DESC LIMIT 1""",
            *[user_info.get("qr_token"), user_info.get("uuid"), salt_for],
        )
        if not salt:
            salt = await db.fetchone(
                """SELECT salt FROM salt_temp WHERE qr_token = $1 AND uuid IS NULL AND salt_for=$2
                    AND created > timezone('utc', now()) ORDER BY created DESC LIMIT 1""",
                *[user_info.get("qr_token"), salt_for],
            )

            if not salt:
                return None

        return salt.get("salt")

    elif user_info.get("pub_key"):
        public_key = user_info["pub_key"]
        if not is_valid_public_key(public_key):
            return None

        query = """SELECT salt FROM salt_temp WHERE pub_key=$1 AND salt_for=$2
                    AND created > timezone('utc', now()) ORDER BY created DESC LIMIT 1"""
        values = [user_info.get("pub_key"), salt_for]
    elif user_info.get("uuid"):
        uuid = user_info["uuid"]
        if not is_valid_uuid(request, uuid):
            return None

        query = """SELECT salt FROM salt_temp WHERE uuid=$1::uuid AND salt_for=$2
                    AND created > timezone('utc', now()) ORDER BY created DESC LIMIT 1"""
        values = [user_info.get("uuid"), salt_for]
    else:
        return None

    salt = await db.fetchone(query, *values)
    if not salt:
        return None

    return salt.get("salt")


async def request_actor_from_auth_service(
    request: Request, db: AsyncDatabaseAdapter, data: dict
):
    if request.app.config.get("AUTH_STANDALONE") or check_if_auth_service(request):
        return None

    request_data = data.copy()
    request_data["service_uuid"] = request.app.config.get("SERVICE_UUID")
    request_data["signature"] = sign_data(
        request.app.config["SERVICE_PRIVATE_KEY"],
        json_dumps(request_data, sort_keys=True),
    )

    try:
        async with httpx.AsyncClient() as client:
            base = await get_auth_domain(db, request, internal=True)
            response = await client.post(
                urljoin(
                    base,
                    "/service/get_actor_by_identificator/",
                ),
                json=request_data,
                headers=get_language_header(request=request),
            )
            response_data = response.json()
    except Exception as e:
        logging_message(
            request,
            message="Error with getting actor from Auth service.\n Exception - %s" % e,
            status=500,
        )
    else:
        if actor := response_data.get("actor"):
            try:
                raw_created = actor.get('created')
                created_dt = None
                if raw_created:
                    try:
                        created_dt = datetime.strptime(raw_created, '%a, %d %b %Y %H:%M:%S %Z')
                    except Exception:
                        created_dt = None
                values = (
                    actor.get('uuid'),
                    created_dt,
                    actor.get('root_perms_signature'),
                    actor.get('initial_key'),
                    actor.get('secondary_keys') if actor.get('secondary_keys') else None,
                    actor.get('uinfo') if actor.get('uinfo') else None,
                    actor.get('actor_type')
                )

                query = """
                    INSERT INTO actor (
                        uuid,
                        created,
                        root_perms_signature,
                        initial_key,
                        secondary_keys,
                        uinfo,
                        actor_type
                    )
                    VALUES (
                        $1::uuid,
                        $2,
                        $3,
                        $4,
                        $5::jsonb,
                        $6::jsonb,
                        $7
                    )
                    ON CONFLICT (uuid) DO NOTHING
                """

                await db.execute(query, *values)

            except Exception as e:
                logging_message(
                    request,
                    message=f"Error with creating user.\n Actor - {actor}\n Exception - {e}",
                    status=500,
                )
            else:
                return actor

    return None


async def update_salt_data(db: AsyncDatabaseAdapter, uuid: str, qr_token: str):
    """
    Update salt with setting actor uuid in database.
    :param uuid: actor uuid
    :param qr_token: qr token
    :return: updated salt or None
    """

    result = await db.fetchone(
        """SELECT EXISTS(SELECT 1 FROM actor WHERE uuid = $1)""", uuid
    )
    if result and result.get("exists"):
        salt = await db.fetchone(
            """UPDATE salt_temp SET uuid = $1 WHERE qr_token = $2 RETURNING *""",
            uuid,
            qr_token,
        )
        if not salt:
            return None

        return salt
    return None


async def insert_or_update_actor_permaction(
    db: AsyncDatabaseAdapter, permissions: Optional[list[dict]]
):
    order = ["permaction_uuid", "service_uuid", "actor_uuid", "value", "params"]
    conflict = ["permaction_uuid", "service_uuid", "actor_uuid"]
    if permissions:
        await insert_update_query(
            db=db,
            order=order,
            conflict=conflict,
            permissions=permissions,
            subject="actor",
        )


async def insert_or_update_group_permaction(
    db: AsyncDatabaseAdapter, permissions: list[dict]
):
    order = [
        "permaction_uuid",
        "service_uuid",
        "actor_uuid",
        "value",
        "weight",
        "params",
    ]
    conflict = ["permaction_uuid", "service_uuid", "actor_uuid"]
    if permissions:
        await insert_update_query(
            db=db,
            order=order,
            conflict=conflict,
            permissions=permissions,
            subject="group",
        )


async def insert_update_query(
    db: "AsyncDatabaseAdapter",
    order: list[str],
    conflict: list[str],
    permissions: list[dict],
    subject: str,
) -> None:
    """
    Build and execute an INSERT ... ON CONFLICT ... DO UPDATE query
    for the given subject's permaction table using asyncpg-style placeholders.
    """
    values: list = []
    placeholders: list[str] = []
    permissions = deepcopy(permissions)

    idx = 1  # asyncpg placeholders start at $1

    for permission in permissions:
        # ensure params is serialized
        permission["params"] = permission.get("params", {})

        # collect values in the order specified
        values.extend(permission.get(item) for item in order)

        # build placeholder group for this row
        row_placeholders = [f"${i}" for i in range(idx, idx + len(order))]
        placeholders.append(f"({', '.join(row_placeholders)})")

        idx += len(order)

    query = f"""
        INSERT INTO {subject}_permaction ({", ".join(order)})
        VALUES {", ".join(placeholders)}
        ON CONFLICT ({", ".join(conflict)})
        DO UPDATE SET {", ".join([f"{key}=EXCLUDED.{key}" for key in order])};
    """

    await db.execute(query, *values)


async def delete_salt(db: AsyncDatabaseAdapter, user_info: dict):
    """
    Delete salt if it was used.
    :param user_info: dictionary with key uuid or pub_key
    :param app: Flask or FastAPI app instance
    :return: True if deleted, False if not
    """

    if user_info.get("pub_key", None):
        query = "DELETE FROM salt_temp WHERE pub_key=$1 RETURNING salt"
        values = user_info.get("pub_key")
    elif user_info.get("uuid", None):
        query = "DELETE FROM salt_temp WHERE uuid=$1 RETURNING salt"
        values = user_info.get("uuid")
    elif user_info.get("qr_token", None):
        query = "DELETE FROM salt_temp WHERE qr_token=$1 RETURNING salt"
        values = user_info.get("qr_token")
    else:
        return False

    salt = await db.fetchall(query, values)

    if not salt:
        return None

    return True


async def update_user(db: AsyncDatabaseAdapter, apt54: dict):
    """
    Update user on client service
    :param apt54: user apt54
    @subm_flow
    """
    data = apt54.get("user_data")
    if data:
        await db.execute(
            """UPDATE actor
                SET uinfo = actor.uinfo::jsonb || $1::jsonb, initial_key = $2, secondary_keys = $3
                WHERE actor.uuid = $4""",
            *[
                data.get("uinfo") if data.get("uinfo") else "{}",
                data.get("initial_key"),
                data.get("secondary_keys"),
                data.get("uuid"),
            ],
        )


async def delete_not_exist_permactions(
    db: AsyncDatabaseAdapter,
    exist_permissions: list[dict],
    subject: str,
):
    """Delete all permactions except existing"""
    query = f"""
        DELETE FROM {subject}_permaction
        WHERE service_uuid = ANY($1::uuid[])
        AND NOT permaction_uuid = ANY($2::uuid[]);
    """

    service_uuids = list()
    permaction_uuids = list()

    for permaction in exist_permissions:
        service_uuids.append(permaction.get("service_uuid"))
        permaction_uuids.append(permaction.get("permaction_uuid"))

    values = list(set(service_uuids)), list(set(permaction_uuids))

    await db.execute(query, *values)


async def delete_old_permactions(db, new_permactions):
    subjects = ["default", "group", "actor"]

    # TODO: A lot of queries here
    for subject in subjects:
        await delete_not_exist_permactions(
            db, exist_permissions=new_permactions, subject=subject
        )


async def insert_or_update_default_permaction(db, permissions: list[dict]):
    order = [
        "permaction_uuid",
        "service_uuid",
        "value",
        "perm_type",
        "description",
        "title",
        "unions",
        "params",
    ]
    conflict = ["permaction_uuid", "service_uuid"]
    if permissions:
        await insert_update_query(db, order, conflict, permissions, "default")


# FIXME: Remove this because its wrapper for flask url_for
def url_for(request: Request, name: str, **path_params: Any):
    try:
        return request.app.url_path_for(name, **path_params)
    except NoMatchFound:
        return None
