import base64
import json
from io import BytesIO
from json import JSONDecodeError
from typing import Optional
from urllib.parse import urljoin

import httpx
import qrcode
from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi_babel import _
from fastapi_utils.cbv import cbv
from pydantic import BaseModel
from typing_extensions import Annotated

from ..core.ecdsa_lib import sign_data, verify_signature
from ..core.exceptions import Auth54ValidationError
from ..core.utils import (
    apt54_expired,
    convert_datetime,
    create_response_message,
    generate_qr_token,
    hash_md5,
    json_dumps,
    validate_phone_number,
)
from ..settings_sample import LANGUAGES_INFORMATION
from .actor import Actor, ActorNotFound
from .database.async_manager import AsyncDatabaseAdapter
from .decorators import admin_only, service_only
from .dependencies import (
    get_db_connection_for_submodule,
    parsed_data,
    set_cross_origin_headers,
)
from .utils import (
    ERP_APP_URL,
    actor_exists,
    check_if_auth_service,
    create_actor,
    create_masquerading_session_token,
    create_new_salt,
    create_session,
    create_session_with_apt54,
    create_temporary_session,
    delete_temporary_session,
    get_apt54,
    get_apt54_locally,
    get_auth_domain,
    get_default_user_group,
    get_depended_services_source,
    get_language_header,
    get_public_key,
    get_salt_from_depended_services,
    get_service_locale,
    get_session_token_by_auxiliary,
    get_static_group,
    get_user_salt,
    is_valid_uuid,
    logging_message,
    request_actor_from_auth_service,
    update_salt_data,
    validate_email,
    validate_login,
)
from .exceptions import Unauthorized
from .validators.auth_validators import (
    APT54Validator,
    AuthQRCodeAuthorizationValidator,
    ClientAuthenticationValidator,
    CreateSessionTokenByUuidValidator,
    CreateSessionValidator,
    GetSessionValidator,
    RegistrationValidator,
    RootAPT54Validator,
)

auth_router = APIRouter(dependencies=[Depends(set_cross_origin_headers)])


auth_router = APIRouter(dependencies=[
    Depends(set_cross_origin_headers)
    ])


class BaseAuth:
    @staticmethod
    async def upgrade_salt_for(
        db: AsyncDatabaseAdapter, salt, actor_uuid, qr_token, salt_for="authentication"
    ):
        await db.execute(
            """
            UPDATE salt_temp
            SET salt_for = $1
            WHERE salt = $2 AND uuid = $3 AND qr_token = $4""",
            salt_for, salt, actor_uuid, qr_token
        )

    @staticmethod
    def parse_login_data(data):
        available_login_types = ("email", "login", "phone_number")
        login_types = []
        login_values = []
        for ltype in available_login_types:
            if data.get(ltype):
                login_types.append(ltype)
                login_values.append(data.get(ltype))
        return login_types, login_values

    @staticmethod
    def validate_login_value(request, login_type, login_value):
        login_value_is_valid = False
        invalid_msg = ""

        if login_type == "email":
            try:
                validate_email(request, login_value)
            except Auth54ValidationError:
                invalid_msg = _("Email you have inputted is invalid. Please check it.")
            else:
                login_value_is_valid = True
        elif login_type == "login":
            if validate_login(request, login_value):
                login_value_is_valid = True
            else:
                invalid_msg = _(
                    "Login you have inputted is invalid. Please check it. "
                    "Login length must be from 3 to 36 and it must contain alphanumeric values, dots or underscores"
                )
        else:
            if validate_phone_number(login_value):
                login_value_is_valid = True
            else:
                invalid_msg = _(
                    "Phone number you have inputted is invalid. Please check it."
                )

        return login_value_is_valid, invalid_msg

    @staticmethod
    async def add_to_own_listing_group(
        db: AsyncDatabaseAdapter, request: Request, actor_data: dict
    ):
        if (
            request.app.config.get("AUTOADD_TO_SERVICE_LISTING_GROUP", True)
            and not actor_data["actor_type"] == "service"
        ):
            result = await db.fetchone(
                "SELECT uinfo FROM actor where initial_key = $1",
                request.app.config.get("SERVICE_PUBLIC_KEY"),
            )
            if result:
                service_uinfo = result["uinfo"]
                uinfo = service_uinfo
                if service_uinfo and uinfo.get("listing_group"):
                    actor_groups = actor_data["uinfo"].get("groups", [])
                    if uinfo.get("listing_group") not in actor_groups:
                        try:
                            from .service_view import AddActorToOwnListingGroup

                            comm = AddActorToOwnListingGroup(
                                request, db, actor_data["uuid"]
                            )
                            await comm.execute()
                        except Exception as e:
                            logging_message(
                                request,
                                message=f"Error during adding actor to service listing group: {e}",
                            )


@cbv(auth_router)
class RegistrationView(BaseAuth):
    """
    Registration with auth service
    @POST Registration user with auth service based on request body@
    @POST_body_request
    {
        "uinfo": {
            "first_name": "test421",
            "last_name": "test421"
        },
        "email": "test421@gmail.com",
        "login": "test421",
        "phone_number": "+111111111112",
        "password": "test421",
        "password_confirmation": "test421",
        "actor_type": "classic_user"
    }
    @
    @POST_body_response
    {
        "user": {
            "actor_type": "classic_user",
            "created": "Fri, 29 Apr 2022 10:44:50 GMT",
            "initial_key": null,
            "root_perms_signature": null,
            "secondary_keys": null,
            "uinfo": {
                "email": "test421@gmail.com",
                "first_name": "test421",
                "groups": [
                    "4c97a2dc-c0df-4af0-a5c7-1753c46ca2e1"
                ],
                "last_name": "test421",
                "login": "test421",
                "password": "6e8877bfa5e3c58f9de018d18ff823ef",
                "phone_number": "+111111111112"
            },
            "uuid": "7c71adbb-4cfe-4e91-b80e-9fcbc0de9812"
        }
    }
    @
    """

    @auth_router.post("/reg/", name="reg")
    async def post(
        self,
        request: Request,
        data: RegistrationValidator,
        db: AsyncDatabaseAdapter = Depends(get_db_connection_for_submodule),
    ):
        """
        POST /reg/ endpoint
        @subm_flow POST /reg/ endpoint
        """

        data = (
            data.model_dump(exclude_none=True) if isinstance(data, BaseModel) else data
        )
        if not check_if_auth_service(request):
            if not request.app.config.get("AUTH_STANDALONE"):
                # Client service registration
                # Adding service default group in user info
                # Adding salt and service uuid in request data and signing data with service private key
                response, status = await self.complete_service_registration(
                    data=data, request=request, db=db
                )
                return JSONResponse(content=response, status_code=status)
        response, status = await self.complete_auth_registration(
            data=data, request=request, db=db
        )

        return JSONResponse(content=jsonable_encoder(response), status_code=status)

    async def complete_service_registration(
        self, data, request: Request, db: AsyncDatabaseAdapter
    ):
        data = await self.collect_data_for_auth(
            request, db, data, salt_for="registration"
        )

        # Send request on auth service registration endpoint
        async with httpx.AsyncClient() as client:
            response = await client.post(
                urljoin(
                    await get_auth_domain(db, request, internal=True), "/reg/"
                ),
                json=data,
                headers=get_language_header(request),
            )
        # Response from auth
        if response.is_success:
            response_data = response.json()
            user = response_data.pop("user")
            # Create user on client service with data from auth service
            try:
                query = "INSERT INTO actor SELECT * FROM jsonb_populate_record(null::actor, $1::jsonb)"
                await db.execute(query, user)
            except Exception as e:
                logging_message(request, message="Exception on creating user! %s" % e)
                logging_message(
                    request,
                    message="Error on creating user. core.auth_view.RegistrationView - POST.\n "
                    "user - %s" % user,
                )
                response = create_response_message(
                    message=_(
                        "Some error occurred while actor registration. "
                        "Please contact the administrator."
                    ),
                    error=True,
                )

                return response, 400

            if data.get("actor_type") == "classic_user":
                response = create_response_message(
                    message=_("You are successfully registered.")
                )
                response["uuid"] = user.get("uuid")
                response["user"] = user
                return response, 200

            content = json.loads(response.text)
            content["uuid"] = user.get("uuid")
            text = json_dumps(content)

            # Upgrade salt for using the same one in authentication
            salt = await update_salt_data(db, user.get("uuid"), data.get("qr_token"))
            await self.upgrade_salt_for(
                db,
                salt=salt.get("salt"),
                actor_uuid=salt.get("uuid"),
                qr_token=data.get("qr_token"),
                salt_for="authentication",
            )
        else:
            text = response.text
        return json.loads(text), response.status_code

    async def complete_auth_registration(
        self, data, request: Request, db: AsyncDatabaseAdapter
    ):
        if data.get("actor_type") == "classic_user":
            response, status = await self.registration_classic_user(
                db, data, request=request
            )
            return response, status

        # Registration user on auth service
        response, status = await self.registration(request, db, data)

        if status == 200:
            salt = await update_salt_data(
                db, response["user"]["uuid"], data.get("qr_token")
            )
            # Update salt from registration to authentication for next step.
            if salt:
                await self.upgrade_salt_for(
                    db,
                    salt=salt.get("salt"),
                    actor_uuid=salt.get("uuid"),
                    qr_token=data.get("qr_token"),
                    salt_for="authentication",
                )
            else:
                logging_message(request, message="Error with salt updating")

        return response, status

    async def registration(
        self, request: Request, db: AsyncDatabaseAdapter, data: dict
    ):
        """
        Registration step two. In this step we check signed salt and if everything is good create user and return uuid
        :param data: dictionary with uuid and signed salt
        :return: response, status: response - dictionary with uuid of error=True flag with error message, status -
        http code
        Registration on auth service"
        @subm_flow Registration step two
        """
        signed_salt = data.get("signed_salt")
        pub_key = data.get("pub_key")
        qr_token = data.get("qr_token")
        if not pub_key or not signed_salt or not qr_token:
            # There is no public key or signed salt. Not full data set
            logging_message(
                request,
                message="Wrong data was sent. core.auth_view.RegistrationView - registration.\n "
                "pub_key - %s, signed_salt - %s, qr_token - %s"
                % (
                    isinstance(pub_key, str),
                    isinstance(signed_salt, str),
                    isinstance(qr_token, str),
                ),
            )
            response = create_response_message(
                message=_("Invalid request data."), error=True
            )
            return response, 400

        # Check if request was sent from client service.
        if_from_client_service_result = await self.check_if_from_client_service(
            request, db, data
        )
        if if_from_client_service_result.get("from_service"):
            if if_from_client_service_result.get("error"):
                if_from_client_service_result.pop("from_service")
                return if_from_client_service_result, 400

            salt = data.get("salt")
        else:
            salt = await get_user_salt(
                request, db, {"qr_token": qr_token}, salt_for="registration"
            )

        if not salt:
            # There is no salt generated for that public key
            logging_message(
                request,
                message="There is no salt. core.auth_view.RegistrationView - registration.\n "
                "qr_token - %s, salt - %s" % (qr_token, salt),
            )
            response = create_response_message(
                message=_(
                    "There is no verification data based on received data. \n "
                    "Please get new QR code."
                ),
                error=True,
            )
            return response, 400

        # Verify salt signature
        if not verify_signature(pub_key, signed_salt, salt):
            # Wrong signature verification
            logging_message(
                request,
                message="Signature verification failed. core.auth_view.RegistrationView - registration.\n",
            )
            response = create_response_message(
                message=_("Signature verification failed."), error=True
            )
            return response, 400

        # Create secure uinfo
        uinfo = await self.create_secure_uinfo(
            request,
            db,
            data,
            if_from_client_service_result.get("from_service"),
            if_from_client_service_result.pop("client_service_listing_group", None),
        )

        if uinfo.get("email"):
            exists_result = await db.fetchone(
                """SELECT EXISTS(SELECT 1 FROM actor WHERE uinfo ->> 'email' = $1)""",
                uinfo.get("email"),
            )
            exists = exists_result.get("exists") if exists_result else False
            if exists:
                logging_message(
                    request,
                    message="User with such email already exists. core.auth_view. "
                    "RegistrationView - registration.\n email - %s"
                    % uinfo.get("email"),
                )
                response = create_response_message(
                    message=_("Actor with such email already exists."), error=True
                )
                return response, 400

            try:
                validate_email(request, uinfo.get("email"))
            except Auth54ValidationError:
                logging_message(
                    request,
                    message="Invalid email was inputed. core.auth_view. "
                    "RegistrationView - registration.\n email - %s"
                    % uinfo.get("email"),
                )
                response = create_response_message(
                    message=_("Email you have inputted is invalid. Please check it."),
                    error=True,
                )
                return response, 400
        else:
            logging_message(
                request,
                message="User with has not input email. core.auth_view. "
                "RegistrationView - registration.\n uinfo - %s" % uinfo,
            )
            response = create_response_message(
                message=_("There is no email in received data."), error=True
            )
            return response, 400

        # Creating user
        try:
            user = await db.fetchone(
                """INSERT INTO actor(initial_key, uinfo) VALUES ($1, $2::jsonb) RETURNING *""",
                pub_key,
                uinfo,
            )
            if user:
                user["created"] = convert_datetime(user["created"])
        except Exception as e:
            logging_message(
                request,
                message="Exception on creating user! RegistrationView - registration. \n Exception - %s"
                % e,
                level="error",
            )
            user = None

        if not user:
            # actor trigger returned None if such public_key already exists
            logging_message(
                request,
                message="Error with creating user. core.auth_view.RegistrationView - registration.\n "
                "pub_key - %s, uinfo - %s" % (pub_key, uinfo),
            )
            response = create_response_message(
                message=_(
                    "Some error occurred while creating actor. "
                    "Please try again or contact the administrator"
                ),
                error=True,
            )
            return response, 400

        response = dict(user=user)
        if not if_from_client_service_result.get("from_service"):
            response["uuid"] = user["uuid"]
        return response, 200

    async def registration_classic_user(
        self, db: AsyncDatabaseAdapter, data: dict, request: Request
    ):
        """
        Classic registration with login/password.
        :param data: email or login or phone_number, password, password_confirmation
        :return: response, status: response - dictionary with created user or error=True flag with error message,
        status - http code
        @subm_flow Classic registration with login/password
        """
        login_types, login_values = self.parse_login_data(data)

        # Check base arguments
        if (
            not login_values
            or not all(login_values)
            or not data.get("password")
            or not data.get("password_confirmation")
        ):
            logging_message(
                request,
                message="Wrong data. core.auth_view.RegistrationView - registration_classic_user.\n "
                "types is %s, values is %s, password - %s, "
                "password_confirmation - %s"
                % (
                    login_types,
                    login_values,
                    isinstance(data.get("password"), str),
                    isinstance(data.get("password_confirmation"), str),
                ),
            )
            response = create_response_message(
                message=_("Invalid request data."), error=True
            )
            return response, 400

        # Verify signature from client service
        if_from_client_service_result = await self.check_if_from_client_service(
            request, db, data
        )
        if if_from_client_service_result.get("from_service"):
            if if_from_client_service_result.get("error"):
                if_from_client_service_result.pop("from_service")
                return if_from_client_service_result, 400

        # Check password
        password = data["password"]
        password_confirmation = data.get("password_confirmation")
        if len(password) < 4:
            response = create_response_message(
                message=_("Password length too short. Minimum 4 characters"), error=True
            )
            return response, 400
        elif password != password_confirmation:
            logging_message(
                request,
                message="Password and password confirmation do not match. "
                "core.auth_view.RegistrationView - registration_classic_user. ",
            )
            response = create_response_message(
                message=_(
                    "Password and password confirmation do not match. Please check it."
                ),
                error=True,
            )
            return response, 400

        # Validate and check unique login values
        for login_type, login_value in zip(login_types, login_values):
            login_value_is_valid, invalid_msg = self.validate_login_value(
                request, login_type, login_value
            )
            if not login_value_is_valid:
                response = create_response_message(message=invalid_msg, error=True)
                return response, 400
            exists_result = await db.fetchone(
                "SELECT EXISTS(SELECT 1 FROM actor WHERE uinfo->>$1 = $2 "
                "AND actor_type = ANY(ARRAY['classic_user', 'user']))",
                login_type,
                login_value,
            )
            exists = exists_result.get("exists") if exists_result else False
            if exists:
                logging_message(
                    request,
                    message=f"User with such {login_type} exists. "
                    f"core.auth_view.RegistrationView - registration_classic_user.\n {login_type} - {login_value}",
                )
                # because of translations
                if login_type == "email":
                    msg = _("Actor with such email already exists")
                elif login_type == "login":
                    msg = _("Actor with such login already exists")
                else:
                    msg = _("Actor with such phone number already exists")
                response = create_response_message(message=msg, error=True)
                return response, 400

        # Validate accepted uinfo
        uinfo = data.get("uinfo")
        if uinfo:
            if not isinstance(uinfo, dict):
                logging_message(
                    request,
                    message="Uinfo is not a dict. "
                    "core.auth_view.RegistrationView - registration_classic_user.\n"
                    "uinfo type - %s" % type(uinfo),
                )
                response = create_response_message(
                    message=_("Invalid request data type."), error=True
                )
                return response, 400
            if any(login_type in uinfo for login_type in login_types):
                logging_message(
                    request,
                    message=f"Some of {login_types} is in uinfo "
                    + ".core.auth_view.RegistrationView - registration_classic_user",
                )
                response = create_response_message(
                    message=_("Invalid parameter for login in optional data."),
                    error=True,
                )
                return response, 400
            if "password" in uinfo:
                logging_message(
                    request,
                    message="Password is in uinfo. "
                    "core.auth_view.RegistrationView - registration_classic_user",
                )
                response = create_response_message(
                    message=_("Invalid parameter password in optional data."),
                    error=True,
                )
                return response, 400

        # Create secure uinfo
        uinfo = await self.create_secure_uinfo(
            request,
            db,
            data,
            if_from_client_service_result.get("from_service"),
            if_from_client_service_result.pop("client_service_listing_group", None),
        )

        # Parse and add login values to uinfo
        for login_type, login_value in zip(login_types, login_values):
            uinfo[login_type] = login_value

        # Hash and add password to uinfo
        password = hash_md5(password)
        uinfo["password"] = password

        # Invite link logic with groups
        invite_link_groups = None
        if data.get("identifier", None):
            invite_link_info = await db.fetchone(
                """SELECT service_uuid, link_uuid FROM invite_link_temp
                    WHERE params->>'identifier' = $1""",
                [data.get("identifier")],
            )

            if invite_link_info:
                service_info = await db.fetchone(
                    """SELECT uinfo->>'service_domain' AS service_domain,
                        initial_key AS initial_key FROM actor WHERE uuid=$1 AND actor_type='service'""",
                    [invite_link_info.get("service_uuid")],
                )

                if service_info:
                    service_domain = service_info["service_domain"]
                    request_data = dict(
                        service_uuid=request.app.config["SERVICE_UUID"],
                        link_uuid=invite_link_info.get("link_uuid"),
                    )
                    request_data["signature"] = sign_data(
                        request.app.config["SERVICE_PRIVATE_KEY"],
                        json_dumps(request_data, sort_keys=True),
                    )
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            urljoin(service_domain, "/get_invite_link_info/"),
                            json=request_data,
                            headers=get_language_header(request=request),
                        )
                    if response.is_success:
                        response_data = json.loads(response.text)
                        link = response_data.get("link")
                        admin_group = await get_static_group(db, "ADMIN")
                        if not isinstance(admin_group, dict) and admin_group.get(
                            "uuid"
                        ) != link.get("group_uuid"):
                            invite_link_groups = [link.get("group_uuid")]

        if invite_link_groups:
            uinfo["groups"] += invite_link_groups

        # Save new classic_user in database
        query = (
            "INSERT INTO actor(uinfo, actor_type) VALUES ($1::jsonb, $2) RETURNING *"
        )
        values = [uinfo, "classic_user"]
        try:
            result = await db.fetchone(query, *values)
            if result:
                user = Actor(request, result)
        except Exception as e:
            logging_message(request, message="Exception on creating user! %s" % e)
            pwd = uinfo.pop("password")
            pwd_confirmation = uinfo.pop("password_confirmation")
            logging_message(
                request,
                message="Error with creating user "
                "core.auth_view.RegistrationView - registration_classic_user.\n "
                "uinfo - %s, password not exists - %s, "
                "password_confirmation not exists - %s"
                % (uinfo, not pwd, not pwd_confirmation),
            )
            response = create_response_message(
                message=_(
                    "Some error occurred while creating actor. Please try again."
                ),
                error=True,
            )
            return response, 400

        response = dict(user=user.to_dict())
        return response, 200

    @staticmethod
    async def collect_data_for_auth(
        request: Request, db: AsyncDatabaseAdapter, data, salt_for: Optional[str] = None
    ):
        if data.get("actor_type", None) != "classic_user":
            data["salt"] = await get_user_salt(
                request, db, {"qr_token": data.get("qr_token")}, salt_for=salt_for
            )

        data["service_uuid"] = request.app.config["SERVICE_UUID"]

        uinfo = data.get("uinfo", {})
        uinfo["registered_on_service_uuid"] = request.app.config["SERVICE_UUID"]
        uinfo["internal_user"] = request.app.config.get(
            "INTERNAL_USERS_AFTER_REGISTRATION", False
        )
        data["uinfo"] = uinfo

        if request.app.config.get("AUTOADD_TO_SERVICE_LISTING_GROUP", True):
            data["add_to_listing_group"] = True

        data["signature"] = sign_data(
            request.app.config["SERVICE_PRIVATE_KEY"], json_dumps(data, sort_keys=True)
        )
        return data

    @staticmethod
    async def create_secure_uinfo(
        request: Request,
        db: AsyncDatabaseAdapter,
        data,
        from_client_service,
        listing_group=None,
    ):
        """
        Getting email/names for actor from accepted_uinfo
        Adding auth default group.
        :param data: request data
        :return: uinfo.
        @subm_flow Create secure uinfo with auth default group and first_name/last_name
        """
        accepted_uinfo = data.get("uinfo", {})
        secure_uinfo = {}

        # Add first_name/last_name
        secure_uinfo["first_name"] = accepted_uinfo.get("first_name", "")
        secure_uinfo["last_name"] = accepted_uinfo.get("last_name", "")

        # Add default group only
        default_group = await get_default_user_group(db, request)
        secure_uinfo["groups"] = [default_group.get("uuid")] if default_group else []

        # Check and add to listing group
        if data.pop("add_to_listing_group", False):
            if listing_group:
                secure_uinfo["groups"].append(listing_group)

        # Add email for actor with type 'user'
        if "email" in accepted_uinfo and data.get("actor_type", "") != "classic_user":
            secure_uinfo["email"] = accepted_uinfo["email"]

        # Add service uuid where actor tried to register
        if from_client_service and "registered_on_service_uuid" in accepted_uinfo:
            secure_uinfo["registered_on_service_uuid"] = accepted_uinfo[
                "registered_on_service_uuid"
            ]
        elif not from_client_service:
            secure_uinfo["registered_on_service_uuid"] = request.app.config[
                "SERVICE_UUID"
            ]

        # Add key whether user will be internal or not
        if from_client_service:
            secure_uinfo["internal_user"] = accepted_uinfo.get("internal_user", False)
        else:
            secure_uinfo["internal_user"] = request.app.config.get(
                "INTERNAL_USERS_AFTER_REGISTRATION", False
            )

        return secure_uinfo

    @staticmethod
    async def check_if_from_client_service(
        request: Request, db: AsyncDatabaseAdapter, data
    ):
        """
        Check if request was sent from client service.
        If request came from client service - verify signature
        :param data: request data
        :return: dict with flag from_service: True/False. If verification error also error True and error_message.
        @subm_flow
        """
        response = dict(from_service=False)
        if "service_uuid" in data:
            query = """SELECT initial_key, uinfo ->> 'listing_group' as listing_group
                        FROM actor
                        WHERE uuid = $1 AND actor_type = 'service'"""
            values = data.get("service_uuid")
            service_info = await db.fetchone(query, values)

            if not service_info:
                logging_message(
                    request,
                    message="Unknown service.\ndata - %s, service_info - %s"
                    % (data, service_info),
                )
                response = create_response_message(
                    message=_("Unknown service."), error=True
                )
                response["from_service"] = True
                return response

            service_pub_key = service_info.get("initial_key")
            signature = data.pop("signature")
            if not verify_signature(
                service_pub_key, signature, json_dumps(data, sort_keys=True)
            ):
                logging_message(
                    request,
                    message="Signature verification error.\n data - %s, signature - %s"
                    % (data, signature),
                )
                response = create_response_message(
                    message=_("Signature verification failed."), error=True
                )
                response["from_service"] = True
                return response

            response["from_service"] = True
            response["client_service_uuid"] = data["service_uuid"]
            response["client_service_listing_group"] = service_info["listing_group"]

        return response


@cbv(auth_router)
class APT54View:
    """
    Authentication with getting apt54
    :group: (06) "02. Authentication process"
    @POST Authentication with getting apt54@
    @POST_body_request
    {
        "step": 1,
        "uuid": "d573cb16-ebc6-47d2-80a2-d5bd76493881"
    }
    @
    @POST_body_response
    {
        "salt": "7b1dfead35b494b882e84c60ec13c570"
    }
    @
    """

    @auth_router.post("/apt54/", name="apt54")
    async def post(
        self,
        request: Request,
        data: APT54Validator,
        db: AsyncDatabaseAdapter = Depends(get_db_connection_for_submodule),
    ):
        data = data.model_dump() if isinstance(data, BaseModel) else data
        if data.get("step", None) and data.get("step", None) == 1 and data.get("uuid"):
            salt = await create_new_salt(
                request, db, {"uuid": data.get("uuid")}, salt_for="authentication"
            )

            if not salt:
                logging_message(
                    request,
                    message="Error with creating salt. core.auth_view.APT54View - POST.\n "
                    "salt - %s, uuid - %s" % (salt, data.get("uuid")),
                )
                response = create_response_message(
                    message=_(
                        "Some error occurred while creating verification data. "
                        "Please try again or contact the administrator."
                    ),
                    error=True,
                )
                return JSONResponse(content=response, status_code=400)

            response = dict(salt=salt)
            return JSONResponse(content=response, status_code=200)

        response, status = await self.authentication(db, data, request=request)

        if status == 200:
            salt = await update_salt_data(db, data.get("uuid"), data.get("qr_token"))
            if not salt:
                logging_message(request, message="Error with salt updating")

        return JSONResponse(content=jsonable_encoder(response), status_code=status)

    async def authentication(
        self, db: AsyncDatabaseAdapter, data: dict, request: Request
    ):
        """
        Authentication step two. In this step check signed salt and if everything is good ask in auth apt54 and return
        it to user
        :param data: dictionary with uuid and signed salt
        :return: response, status: response - dictionary with apt54 of error=True flag with error message, status - http
        code
        Validate received data
        """
        signed_salt = data.get("signed_salt", None)
        uuid = data.get("uuid", None)
        qr_token = data.get("qr_token", None)
        step = data.get("step", None)

        if not uuid or not signed_salt or (not step == 2 and not qr_token):
            # There is no uuid or signed salt. Not full data set
            logging_message(
                request,
                message="Wrong data was sent. core.auth_view.APT54View - authentication.\n "
                "uuid - %s, signed_salt not exists - %s, "
                "step - %s, qr_token - %s" % (uuid, not signed_salt, step, qr_token),
            )
            response = create_response_message(
                message=_("Invalid request data."), error=True
            )
            return response, 400

        if step:
            salt = await get_user_salt(
                request, db, {"uuid": uuid}, salt_for="authentication"
            )
        else:
            salt = await get_user_salt(
                request,
                db,
                {"qr_token": qr_token, "uuid": uuid},
                salt_for="authentication",
            )

        if not salt:
            # There is no salt generated for that public key
            logging_message(
                request,
                message="Wrong with getting salt. core.auth_view.APT54View - authentication.\n "
                "salt - %s, uuid - %s, qr_token - %s" % (salt, uuid, qr_token),
            )
            response = create_response_message(
                message=_(
                    "There is no verification data based on received data. \n "
                    "Please get new QR code. "
                ),
                error=True,
            )
            return response, 400

        # Getting user public key and keys if they were regenerated
        initial_key, secondary_keys = await get_public_key(db, uuid)
        if not initial_key and not secondary_keys:
            # User has no public key
            logging_message(
                request,
                message="User has no public key. core.auth_view.APT54View - authentication.\n "
                "uuid - %s, initial_key - %s, "
                "secondary_keys - %s" % (uuid, initial_key, secondary_keys),
            )
            response = create_response_message(
                message=_(
                    "There is no your public key for your actor. "
                    "Please contact the administrator."
                ),
                error=True,
            )
            return response, 400

        # Verify salt signature with primary public key
        if verify_signature(initial_key, signed_salt, salt):
            # Signature verification passed with initial key
            # Getting apt54 from auth service
            return await self.get_apt54_with_response(db, uuid, request=request)

        else:
            # Service use only primary key
            if request.app.config.get("PRIMARY_KEY_ONLY"):
                # Error response
                # Important service uses only primary initial key
                logging_message(
                    request,
                    message="Signature verification error Because PRIMARY_KEY_ONLY is True and "
                    "verification by initial_key failed. "
                    "core.auth_view.APT54View - authentication.\n ",
                )
                response = create_response_message(
                    message=_("Signature verification failed."), error=True
                )
                return response, 400

            if secondary_keys:
                for public_key in secondary_keys:
                    # Verify signature with secondary keys
                    # Check signature with secondary generated keys
                    if verify_signature(public_key, signed_salt, salt):
                        # Getting apt54 from auth service
                        return await self.get_apt54_with_response(
                            db, uuid, request=request
                        )

        logging_message(
            request,
            message="Signature verification error. core.auth_view.APT54View - authentication.\n ",
        )
        response = create_response_message(
            message=_("Signature verification failed."), error=True
        )
        return response, 400

    @staticmethod
    async def get_apt54_with_response(
        db: AsyncDatabaseAdapter, uuid: str, request: Request
    ):
        if request.app.config.get("AUTH_STANDALONE"):
            apt54, status_code = await get_apt54_locally(request, db, uuid=uuid)
        else:
            apt54, status_code = await get_apt54(request, db, uuid=uuid)
        if status_code == 452:
            logging_message(
                request,
                message="Error with getting apt54. There is no such user with uuid - %s. "
                "core.auth_view.APT54View - get_apt54_with_response.\n" % uuid,
            )
            response = create_response_message(
                message=_("There is no such actor. Please contact the administrator"),
                error=True,
            )
            status = 400
        elif not apt54:
            logging_message(
                request,
                message="Error with getting apt54. core.auth_view.APT54View - get_apt54_with_response.\n "
                "uuid - %s" % uuid,
            )
            response = create_response_message(
                message=_(
                    "Auth service is unreachable. "
                    "Please try again or contact the administrator."
                ),
                error=True,
            )
            status = 400
        elif status_code == 200:
            status = 200
            response = dict(apt54=json_dumps(apt54))
        else:
            logging_message(
                request,
                message="Error with getting apt54. core.auth_view.APT54View - get_apt54_with_response.\n "
                "uuid - %s" % uuid,
            )
            response = create_response_message(
                message=_(
                    "Some error occurred with getting your authentication token. "
                    "Please try again or contact the administrator."
                ),
                error=True,
            )
            status = 400
        return response, status


@cbv(auth_router)
class ClientAuthenticationView(BaseAuth):
    """
    Authorization on client service
    @POST Authorization on client service@
    @POST_body_request
    {
        "step": "identification",
        "email": "qwerty@gmail.com",
        "actor_type": "classic_user"
    }
    @
    @POST_body_response
    {
        "temporary_session": "7qvJT9E9p8DzcOhBQ3xhhs9O5fuAafpX"
    }
    @
    """

    @auth_router.post("/auth/", name="auth")
    async def post(
        self,
        request: Request,
        data: ClientAuthenticationValidator,
        db: AsyncDatabaseAdapter = Depends(get_db_connection_for_submodule),
    ):
        """
        POST /auth/ endpoint
        @subm_flow  POST /auth/ endpoint
        """
                #################
        #FIXME TEST
        ###################
        gen = get_db_connection_for_submodule(request)
        db = await gen.__anext__()
        #################
        #FIXME TEST
        ###################
        self.data = data.model_dump() if isinstance(data, BaseModel) else data
        step = self.data.pop("step", None)
        if step not in ("identification", "check_secret"):
            step = None
        self.qr_token = self.data.pop("qr_token", None)

        if step == "identification" or self.qr_token:
            result = await self.identificate_actor(db, request)
            if not result.get("error"):
                if not self.qr_token:
                    result = await self.create_trust_element(
                        db,
                        actor_uuid=result.get("uuid"),
                        actor_type=result.get("actor_type"),
                        request=request,
                    )
                    status_code = 200
                else:
                    self.qr_user = result
            else:
                status_code = 400

        if step == "check_secret" or hasattr(self, "qr_user"):
            result = await self.check_secret(db, request=request)
            if not result.get("error"):
                user_data = result["user_data"]
                result = await create_session(
                    db=db,
                    request=request,
                    user_data=user_data,
                    auxiliary_token=self.qr_token,
                    depended_info=self.data.get("depended_services"),
                )
                if not result.get("error"):
                    await self.add_to_own_listing_group(db, request, user_data)
                    status_code = 200
                else:
                    status_code = 403
            else:
                status_code = 400

        if not step and not self.qr_token:
            result = create_response_message(_("Invalid request data."), error=True)
            status_code = 400

        if hasattr(self, "qr_user"):
            await update_salt_data(db, self.qr_user["uuid"], self.qr_token)
            result["apt54"] = self.data.get("apt54")  # FIXME: temporary solution

        response = JSONResponse(result, status_code)
        return response

    async def identificate_actor(self, db: AsyncDatabaseAdapter, request: Request):
        actor_type = self.data.get("actor_type")
        values = []
        conditions = []

        if actor_type == "classic_user":
            login_types, login_values = self.parse_login_data(self.data)

            if not login_values or not all(login_values):
                logging_message(
                    request,
                    message=f"Wrong data was sent. Login types={login_types}, login values={login_values}",
                )
                return create_response_message(
                    message=_("Invalid request data."), error=True
                )

            for login_type, login_value in zip(login_types, login_values):
                login_value_is_valid, invalid_msg = self.validate_login_value(
                    request, login_type, login_value
                )
                if not login_value_is_valid:
                    return create_response_message(message=invalid_msg, error=True)

            for idx, (login_type, login_value) in enumerate(
                zip(login_types, login_values), start=1
            ):
                conditions.append(f"uinfo ->> ${idx} = ${idx + len(login_types)}")
                values.append(login_type)
                values.append(login_value)

            conditions.append("actor_type = 'classic_user'")

        else:
            uuid = self.data.get("uuid")
            if not uuid:
                if apt54_data := self.data.get("apt54"):
                    apt54 = (
                        apt54_data
                        if isinstance(apt54_data, dict)
                        else json.loads(apt54_data)
                    )
                    uuid = apt54["user_data"].get("uuid")

            if not uuid or not is_valid_uuid(request, uuid):
                logging_message(request, message=f"Wrong data was sent. UUID={uuid}")
                return create_response_message(
                    message=_("Invalid request data."), error=True
                )

            conditions.append("uuid = $1")
            values.append(uuid)

        query = f"SELECT * FROM actor WHERE {' AND '.join(conditions)}"

        actor = await db.fetchone(query, *values)

        if not actor:
            actor = await request_actor_from_auth_service(
                request=request,
                db=db,
                data=self.data if actor_type == "classic_user" else {"uuid": uuid},
            )
            if not actor:
                if actor_type == "classic_user":
                    logging_message(
                        request,
                        message=f"Error with getting user.\n {login_types} - {login_values}",
                    )
                    if login_types == ["email"]:
                        msg = _("There is no actor with such email. Please check it.")
                    elif login_types == ["login"]:
                        msg = _("There is no actor with such login. Please check it.")
                    elif login_types == ["phone_number"]:
                        msg = _(
                            "There is no actor with such phone number. Please check it."
                        )
                    elif login_types == ["email", "login"]:
                        msg = _(
                            "There is no actor with such email and login. Please check it."
                        )
                    else:
                        msg = _("There is no actor with such data. Please check it.")
                else:
                    logging_message(
                        request, message=f"Error with getting actor.\n UUID={uuid}"
                    )
                    msg = _("There is no actor with such uuid.")
                return create_response_message(message=msg, error=True)

        return actor

    async def create_trust_element(
        self, db: AsyncDatabaseAdapter, actor_uuid, actor_type, request: Request
    ):
        if actor_type == "classic_user":
            return {
                "temporary_session": await create_temporary_session(
                    db, request=request, actor_uuid=actor_uuid
                )
            }
        else:
            salt = await create_new_salt(
                request, db, {"uuid": actor_uuid}, salt_for="authentication"
            )
            if not salt:
                logging_message(
                    request,
                    message="Error with creating salt.\n"
                    "salt - %s, actor_uuid - %s" % (salt, actor_uuid),
                )
                response = create_response_message(
                    message=_("There is no verification data based on received data."),
                    error=True,
                )
            else:
                response = {"salt": salt}
                if actor_type != "service":
                    if depended_services_salts := await get_salt_from_depended_services(
                        data=self.data, request=request
                    ):
                        response.update(
                            {
                                "depended_services": depended_services_salts,
                            }
                        )
            return response

    async def check_secret(self, db: AsyncDatabaseAdapter, request: Request):
        if self.data.get("actor_type") == "classic_user":
            temporary_session = self.data.get("temporary_session")
            if temporary_session:
                user_data = await db.fetchone(
                    """SELECT * FROM actor
                        WHERE actor_type='classic_user' AND uuid = (SELECT actor_uuid
                        FROM temporary_session
                        WHERE temporary_session=$1)""",
                    temporary_session,
                )
                await delete_temporary_session(
                    db, request=request, temporary_session=temporary_session
                )
                if user_data:
                    uinfo = user_data["uinfo"]
                    hashed_password = uinfo.get("password")
                    if hash_md5(hashed_password + temporary_session) == self.data.get(
                        "password"
                    ):
                        return {"user_data": user_data}
            return create_response_message(
                message=_("Password verification failed."), error=True
            )

        else:
            signed_salt = self.data.get("signed_salt")
            if self.qr_token:
                user = self.qr_user
            else:
                user = await db.fetchone(
                    "SELECT * FROM actor WHERE uuid = $1", self.data.get("uuid")
                )
                if not user:
                    response = create_response_message(
                        message=_("There is no actor with such uuid."), error=True
                    )
                    return response
            uuid = user["uuid"]

            salt = await get_user_salt(
                request,
                db,
                {"qr_token": self.qr_token, "uuid": uuid},
                salt_for="authentication",
            )
            if not salt:
                # There is no salt generated for that public key
                logging_message(
                    request,
                    message="Error with getting salt during authentication process.\n "
                    "UUID - %s, qr_token - %s" % (uuid, self.qr_token),
                )
                response = create_response_message(
                    message=_("There is no verification data based on received data."),
                    error=True,
                )
                return response

            # Getting user public key and keys if they were regenerated
            initial_key, secondary_keys = await get_public_key(db, uuid)

            # Actor has public keys
            if not initial_key and not secondary_keys:
                logging_message(
                    request,
                    message="Error with getting initial_key. initial_key - %s"
                    % initial_key,
                )
                response = create_response_message(
                    message=_(
                        "There is no your public key for your actor. "
                        "Please contact the administrator.\n"
                    ),
                    error=True,
                )
                return response

            # Verify signed salt with primary public key
            signature_verified = False
            if verify_signature(initial_key, signed_salt, salt):
                signature_verified = True
            else:
                if request.app.config.get("PRIMARY_KEY_ONLY") and secondary_keys:
                    # Important service uses only primary initial key
                    logging_message(
                        request,
                        message="Signature verification error because PRIMARY_KEY_ONLY is True and "
                        "verification by initial_key failed.\n",
                    )
                elif secondary_keys:
                    for public_key in secondary_keys:
                        # Check signature with secondary generated keys
                        # Verify salt signature with secondary keys
                        if verify_signature(public_key, signed_salt, salt):
                            signature_verified = True
                            break

            if signature_verified:
                return {"user_data": user}
            else:
                return create_response_message(
                    message=_("Signature verification failed."), error=True
                )


@cbv(auth_router)
class RootAPT54View:
    """
    @POST Identificate actor and create session with Root self signed APT54@
    @POST_body_request
    {
        "apt54": {
            "signature": "304402202ad85986124e2777bae8a13ad693392e0bb0f27ac367f3d07d3de7534f7aa9350220255e0650af",
            "expiration": "2024-12-24 10:36:04",
            "user_data": {
                "uuid": "76715295-e362-4623-8efc-929ea661d5e9",
                "uinfo": {
                    "email": "example3@mail.ru",
                    "groups": ["d0d53af4-eb05-4e1c-95f1-935ff453dc37"],
                    "password": "e745a6bad4ffe5a1b35aac134ea148c7",
                    "last_name": "string",
                    "first_name": "string"
                    },
                "created": "2024-11-25T12:49:17.965",
                "actor_type": "classic_user",
                "initial_key": "049c5597ed9f53f2311c64f1501cf8d087ca1c464a790365ff37b8421b78a8ed68bba0d41119",
                "secondary_keys": null,
                "root_perms_signature": "3046022100fdb9029b6937a6befe6a2e8ed429ce79336cbfa0f1c4e6e47a5fb11b3b"
            }
        },
        "create_session": true
    }
    @
    @POST_body_response
    {
        "message": "Successfully executed",
        "session_token": "k7JsqFhbjTtcZD3YKnG6O9y406myhWHl",
        "expiration": "2024-12-26 11:42:12"
    }
    @
    """

    @auth_router.post("/apt54/root/", name="root_apt54")
    async def post(
        self,
        request: Request,
        data: RootAPT54Validator,
        db: AsyncDatabaseAdapter = Depends(get_db_connection_for_submodule),
    ):
        data = data.model_dump() if isinstance(data, BaseModel) else data
        apt54 = data.get("apt54")
        status_code = None
        if apt54 and isinstance(apt54, dict):
            apt54_signature = apt54.get("signature")
            user_data = apt54.get("user_data", {})
            root_perms_signature = user_data.get("root_perms_signature")
            initial_key = user_data.get("initial_key")
            uuid = user_data.get("uuid")
            # Check apt54 values
            if all((apt54_signature, root_perms_signature, initial_key, uuid)):
                service_public_key = (
                    request.app.config["AUTH_PUB_KEY"]
                    if not request.app.config.get("AUTH_STANDALONE")
                    else request.app.config["SERVICE_PUBLIC_KEY"]
                )
                # Check actor is root
                if verify_signature(
                    service_public_key, root_perms_signature, uuid + initial_key
                ):
                    user_data = json_dumps(user_data, sort_keys=True)
                    expiration = apt54.get("expiration")
                    verifying_data = str(user_data) + str(expiration)
                    # Verify apt54 signature
                    if verify_signature(initial_key, apt54_signature, verifying_data):
                        # Check apt54 expiration
                        if not apt54_expired(expiration):
                            query = """SELECT * FROM actor WHERE uuid = $1"""
                            values = [uuid]
                            actor = await db.fetchone(query, values)
                            if not actor:
                                actor = await create_actor(request, db, apt54)
                            if actor:
                                result = create_response_message(
                                    _("Successfully executed")
                                )
                                status_code = 200
                                if data.get("create_session"):
                                    session_data = await create_session(
                                        db,
                                        request,
                                        actor,
                                    )
                                    result.update(session_data)
                            else:
                                result = (
                                    create_response_message(
                                        _("Error with getting actor"), error=True
                                    ),
                                )
                        else:
                            result = (
                                create_response_message(
                                    _("APT54 expired."), error=True
                                ),
                            )
                    else:
                        result = (
                            create_response_message(
                                _("Signature verification failed."), error=True
                            ),
                        )
                else:
                    result, status_code = (
                        create_response_message(_("Actor must be Root"), error=True),
                        403,
                    )
            else:
                result = (
                    create_response_message(_("Invalid APT54 was sent."), error=True),
                )
        else:
            result = (create_response_message(_("Invalid request data."), error=True),)
        return JSONResponse(
            jsonable_encoder(result), status_code=status_code if status_code else 400
        )


@cbv(auth_router)
class SaveSession:
    """
    @POST Save session in cookies with flask session module based on request body@
    @POST_body_request
    {
        "session_token": "2dfTUcgbyj2GGIUc2RuanS8jkxGO6Qni"
    }
    @
    @POST_body_response
    {
        "message": "Session token successfully saved."
    }
    @
    """

    @auth_router.post("/save_session/", name="save_session")
    async def post(
        self,
        request: Request,
        data: CreateSessionValidator,
        db: AsyncDatabaseAdapter = Depends(get_db_connection_for_submodule),
    ):
        """
        Save session in cookies with flask session module.
        @subm_flow Save session in cookies with flask session module.
        """
        session_token = data.model_dump().get("session_token")

        exists_result = await db.fetchone(
            """SELECT EXISTS(SELECT 1 FROM service_session_token WHERE session_token = $1)""",
            session_token,
        )
        exists = exists_result.get("exists") if exists_result else False
        if exists:
            request.session["session_token"] = session_token
            message = _("Session token successfully saved.")
        else:
            message = _(f"Unknow session token - {session_token}")
            logging_message(request, message=message, level="warning")

        response = dict(message=message)
        return JSONResponse(content=jsonable_encoder(response), status_code=200)


@cbv(auth_router)
class GetSession:
    """
    @POST Get session based on request body@
    @POST_body_request
    {
        "qr_token": "Wfkjwenk4ksjg6oo6",
        "temporary_session": "7h4s5kjI5CFU8KLD74TMc1QSVHWP8Sk0"
    }
    @
    @POST_body_response
    {
        "session_token": "XVKKdV86W8uHmdnAfQ1nWSxqbfECHpiQ"
    }
    @
    """

    @auth_router.post("/get_session/", name="get_session")
    async def post(
        self,
        request: Request,
        data: GetSessionValidator,
        db: AsyncDatabaseAdapter = Depends(get_db_connection_for_submodule),
    ):
        """
        Get session by qr code and temporary session.
        :return: session token
        @subm_flow
        """

        data = data.model_dump()
        if data.get("qr_token"):
            session_token = await get_session_token_by_auxiliary(
                db, data.get("qr_token")
            )
            if not session_token:
                session_token = dict(message=_("There is no session token."))
            response = session_token

        temporary_session = data.get("temporary_session")

        if temporary_session:
            exists_result = await db.fetchone(
                """SELECT EXISTS(SELECT 1 FROM temporary_session WHERE temporary_session = $1)""",
                temporary_session,
            )
            exists = exists_result.get("exists") if exists_result else False
            if exists:
                session_token = await get_session_token_by_auxiliary(
                    db, temporary_session
                )
                if session_token:
                    await db.execute(
                        """UPDATE service_session_token SET auxiliary_token = NULL WHERE auxiliary_token = $1""",
                        temporary_session,
                    )

                await delete_temporary_session(
                    db, request=request, temporary_session=temporary_session
                )
                response = session_token

        return JSONResponse(content=jsonable_encoder(response), status_code=200)


@cbv(auth_router)
class AuthorizationView:
    """
    @GET Submodule Biom mode. Get login template.
    Automatically adding js, css scripts from static folder according to app config.@
    @GET_body_request
    Content-Type: None
    @
    @GET_body_response
    Status Code: 200
    Content-Type: text/html; charset=utf-8
    Content-Length: 125087
    Access-Control-Allow-Origin: *
    Vary: Cookie
    @
    """

    @auth_router.get("/authorization/", name="authorization")
    async def get(
        self,
        request: Request,
        db: AsyncDatabaseAdapter = Depends(get_db_connection_for_submodule),
    ):
        """
        Get login template.
        Automatically adding js, css scripts from static folder according to app config.
        :param kwargs: dict. OPTIONAL. Example:
        {
            "registration_url": https://example.com/registration or /registration/ or url_for('registration'),
            "authentication_url": https://example.com/authentication or /authentication/ or url_for('authentication'),
            "redirect_url_after_authentication": /some_url/ or /,
            "save_session_url": https://example.com/save or /save/ or url_for('save'),
            "get_qr_url": https://example.com/qr or /qr/ or url_for('qr'),
            "qr_login_url": https://example.com/qr_login or /qr_login/ or url_for('qr_login'),
            "sso_generation_url": https://example.com/sso or /sso/ or url_for('sso'),
            "sso_login_url": https://example.com/sso_login or /sso_login/ or url_for('sso_login'),
        }
        :return: template
        @subm_flow
        """

        self.service_domain = request.app.config.get("SERVICE_DOMAIN")
        self.is_standalone = request.app.config.get("AUTH_STANDALONE", False)
        self.is_auth_service = check_if_auth_service(request)
        self.sso_mode = request.app.config.get("SSO_MODE", True)
        kwargs = await request.form()
        # default context
        context = {
            "standalone": self.is_standalone,
            "is_auth_service": self.is_auth_service,
            "sso_mode": self.sso_mode,
            "current_language": self.define_language(request),
            "language_information": request.app.config.get("LANGUAGES_INFORMATION", []),
            "service_name": request.app.config.get(
                "SERVICE_NAME", "service"
            ).capitalize(),
        }

        # static files with service domain
        context.update(await self.get_static_files_urls(db, request=request))

        # getting all urls with services domains
        context.update(await self.get_urls(db, request=request, **kwargs))

        if not self.is_standalone:
            context.update(await self.get_qr_token_content(db, request=request))
            context["depended_services"] = await self.get_depended_services(
                db, request=request
            )

        return request.app.state.templates.TemplateResponse(
            request=request, name="auth.html", context=context
        )

    def define_language(self, request: Request):
        language_information = request.app.config.get(
            "LANGUAGES_INFORMATION", LANGUAGES_INFORMATION
        )
        current_language = None
        for language in language_information:
            if language.get("code") == get_service_locale(request):
                current_language = language

        if not current_language:
            current_language = {"code": "en", "name": "English"}
        return current_language

    def _static_link(self, request: Request, name: str) -> str:
        """
        Build full URL for a static file served by auth_submodule.
        """
        return urljoin(
            self.service_domain,
            request.url_for("auth_submodule.static", path=name).path,
        )

    async def get_static_files_urls(self, db: AsyncDatabaseAdapter, request: Request):
        styles = [
            self._static_link(request, "css/auth.css"),
            self._static_link(request, "css/materialdesignicons.min.css"),
        ]
        scripts = [
            self._static_link(request, "js/x-notify.js"),
            self._static_link(request, "js/md5.min.js"),
            self._static_link(request, "js/default_authorization.js"),
        ]

        if not self.is_standalone:
            scripts += [
                self._static_link(request, "js/qrLib.js"),
                self._static_link(request, "js/qr_code_authorization.js"),
            ]
            if not self.is_auth_service and self.sso_mode:
                scripts.append(self._static_link(request, "js/sso_authorization.js"))

        return {"styles": styles, "scripts": scripts}

    def _make_url(self, domain: str, endpoint: str, request: Request) -> str:
        """
        Build full URL for a given domain and FastAPI endpoint.
        """
        return urljoin(domain, request.url_for(endpoint).path)

    async def get_urls(self, db: AsyncDatabaseAdapter, request: Request, **kwargs):
        def make_url(endpoint: str) -> str:
            return urljoin(self.service_domain, endpoint)

        urls = {
            "authentication_url": make_url(
                kwargs.get(
                    "authentication_url",
                    request.url_for("ClientAuthenticationView.auth").path,
                )
            ),
            "registration_url": make_url(
                kwargs.get(
                    "registration_url", request.url_for("RegistrationView.reg").path
                )
            ),
            "redirect_url_after_authentication": kwargs.get(
                "redirect_url_after_authentication",
                request.app.config.get("REDIRECT_URL_AFTER_AUTHENTICATION", "/"),
            ),
        }

        if not self.is_standalone:
            urls["get_qr_url"] = make_url(
                kwargs.get("get_qr_url", request.url_for("GetQRCodeView.qr-code").path)
            )
            urls["qr_login_url"] = make_url(
                kwargs.get(
                    "qr_login_url",
                    request.url_for("AuthQRCodeAuthorizationView.auth_qr_login").path,
                )
            )
            urls["save_session_url"] = make_url(
                kwargs.get(
                    "save_session_url", request.url_for("SaveSession.save_session").path
                )
            )
            if not self.is_auth_service and self.sso_mode:
                urls["sso_generation_url"] = make_url(
                    kwargs.get(
                        "sso_generation_url",
                        request.url_for("AuthSSOGenerationView.auth-sso").path,
                    )
                )
                urls["sso_login_url"] = make_url(
                    kwargs.get(
                        "sso_login_url",
                        request.url_for("AuthSSOAuthorizationView.auth_sso_login").path,
                    )
                )

        return urls

    async def get_depended_services(self, db: AsyncDatabaseAdapter, request: Request):
        depended_services = []
        depended_services_source = get_depended_services_source(request)

        for name, domain in depended_services_source.items():
            service_data = {
                "name": name.capitalize(),
                "authentication_url": self._make_url(
                    domain, "ClientAuthenticationView.auth", request
                ),
                "save_session_url": self._make_url(
                    domain, "SaveSession.save_session", request
                ),
            }
            if not self.is_auth_service and self.sso_mode:
                service_data["sso_generation_url"] = self._make_url(
                    domain, "AuthSSOGenerationView.auth-sso", request
                )
            depended_services.append(service_data)

        return depended_services

    async def get_qr_token_content(self, db: AsyncDatabaseAdapter, request: Request):
        # get full content from GetQRCodeView
        auth_response = await GetQRCodeView().get(
            request=request, data=dict(qr_type="authentication"), db=db
        )
        authentication_content = json.loads(auth_response.body)

        reg_response = await GetQRCodeView().get(
            request, dict(qr_type="registration"), db
        )
        registration_content = json.loads(reg_response.body)
        registration_content["depended_services"] = authentication_content.get(
            "depended_services"
        )

        # get token only data with depended services if exists
        authentication_qr_token = {
            "qr_token": authentication_content.get("qr_token"),
            "qr_type": "authentication",
        }
        registration_qr_token = {
            "qr_token": registration_content.get("qr_token"),
            "qr_type": "registration",
        }
        if authentication_content.get("depended_services"):
            authentication_qr_token["depended_services"] = {}
            registration_qr_token["depended_services"] = {}
            for name, data in authentication_content.get("depended_services").items():
                authentication_qr_token["depended_services"][name] = {
                    "qr_token": data.get("qr_token"),
                    "qr_type": "authentication",
                }
                registration_qr_token["depended_services"][name] = {
                    "qr_token": data.get("qr_token"),
                    "qr_type": "registration",
                }

        return {
            "authentication_content": authentication_content,
            "authentication_qr_token": authentication_qr_token,
            "registration_content": registration_content,
            "registration_qr_token": registration_qr_token,
        }


@cbv(auth_router)
class GetQRCodeView:
    """
    QR code generation
    Parameters: - qr_token - salt - domain - biom_uuid"
    @GET QR code generation@
    @GET_body_request
    Content-Type: None
    @
    @GET_body_response
    {
        "qr_code": "iVBORw0KGgoAAAANSUhEUgAAAhIAAAISAQAAAACxRhsSAAAEzklEQVR"
    }
    @
    """

    @auth_router.get("/get_qr_code/", name="qr-code")
    async def get(
        self,
        request: Request,
        data: Annotated[dict, Depends(parsed_data)],
        db: AsyncDatabaseAdapter = Depends(get_db_connection_for_submodule),
    ):
        if request.query_params.get("qr_type", None) == "application":
            img_io = self.generate_qr_image(ERP_APP_URL)
            response = dict(
                qr_code=base64.b64encode(img_io.getvalue()).decode(),
            )
            return JSONResponse(content=jsonable_encoder(response), status_code=200)

        query = """SELECT uinfo->>'service_domain' AS service_domain FROM actor WHERE uuid = $1"""
        service_domain = await db.fetchone(
            query, request.app.config.get("SERVICE_UUID")
        )
        if not service_domain:
            raise ActorNotFound

        service_domain = service_domain["service_domain"]
        registration_url = (
            data.get("registration_url")
            if data.get("registration_url")
            else urljoin(
                service_domain,
                request.url_for("RegistrationView.reg").path,
            )
        )
        apt54_url = urljoin(
            service_domain,
            request.url_for("APT54View.apt54").path,
        )
        authentication_url = (
            data.get("authentication_url")
            if data.get("authentication_url")
            else urljoin(
                service_domain,
                request.url_for("ClientAuthenticationView.auth").path,
            )
        )
        about_url = (
            data.get("about_url")
            if data.get("about_url")
            else urljoin(
                service_domain,
                request.url_for("AboutView.about").path,
            )
        )

        qr_type = None

        if request.query_params.get("qr_type"):
            if request.query_params.get("qr_type") not in [
                "registration",
                "authentication",
            ]:
                logging_message(
                    request,
                    message="Error with getting qr_type from request args. core.auth_view.QRCodeView - "
                    "GET.\n request.query_params - %s" % request.query_params,
                )
                response = create_response_message(
                    message=_(
                        "Unknown QR type. "
                        "Please try again or contact the administrator."
                    ),
                    error=True,
                )
                return JSONResponse(content=response, status_code=400)

            qr_type = request.query_params.get("qr_type")

        if data.get("qr_type") and not qr_type:
            if data.get("qr_type") not in ["registration", "authentication"]:
                logging_message(
                    request,
                    message="Error with getting qr_type from kwargs. core.auth_view.QRCodeView - "
                    "GET.\n data - %s" % data,
                )
                response = create_response_message(
                    message=_(
                        "Unknown QR type. "
                        "Please try again or contact the administrator."
                    ),
                    error=True,
                )
                return JSONResponse(content=response, status_code=400)

            qr_type = data.get("qr_type")

        if not qr_type:
            logging_message(
                request,
                message="Error with getting qr_type from request args and kwargs. "
                "core.auth_view.QRCodeView - GET.\n",
            )
            response = create_response_message(
                message=_(
                    "There is no QR type. "
                    "Please try again or contact the administrator."
                ),
                error=True,
            )
            return JSONResponse(content=response, status_code=400)

        qr_token = generate_qr_token()
        salt = await create_new_salt(
            request, db, user_info={"qr_token": qr_token}, salt_for=qr_type
        )
        if not salt:
            logging_message(
                request,
                message="Error with creating salt. core.auth_view.QRCodeView - GET.\n salt - %s"
                % salt,
            )
            response = create_response_message(
                message=_(
                    "Some error occurred while creating verification data. "
                    "Please try again or contact the administrator."
                ),
                error=True,
            )
            return JSONResponse(content=jsonable_encoder(response), status_code=400)

        if qr_type == "registration":
            data = dict(
                qr_token=qr_token,
                salt=salt,
                about_url=about_url,
                registration_url=registration_url,
                apt54_url=apt54_url,  # TODO: remove it later
                authentication_url=authentication_url,
                auth_domain=await get_auth_domain(db, request),
            )
            response = data
        else:
            response = dict(
                qr_token=qr_token,
                salt=salt,
                about_url=about_url,
                apt54_url=apt54_url,  # TODO: remove it later
                authentication_url=authentication_url,
                auth_domain=await get_auth_domain(db, request),
            )
            response.update(
                {
                    "depended_services": await self.get_depended_qr_info(
                        db, request=request
                    )
                }
            )
        return JSONResponse(content=jsonable_encoder(response), status_code=200)

    async def get_depended_qr_info(self, db: AsyncDatabaseAdapter, request: Request):
        services_info = dict()
        depended_services_source = get_depended_services_source(request)
        for name, domain in depended_services_source.items():
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        urljoin(domain, "/get_qr_code/"),
                        params={"qr_type": "authentication"},
                    )
                    services_info.update({name: dict(response.json())})
            except Exception:
                continue
        return services_info

    @staticmethod
    def generate_qr_image(data):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)

        img = qr.make_image()
        img_io = BytesIO()
        img.save(img_io, "PNG")
        img_io.seek(0)
        return img_io


@cbv(auth_router)
class AuthQRCodeAuthorizationView:
    """
    @POST Login with QR code@
    @POST_body_request
    Content-Type: application/x-www-form-urlencoded
    {
        "qr_token": "Wfkjwenk4ksjg6oo6",
        "qr_type": "authentication",
        "depended_services": {
            "uuid":"76715295-e362-4623-8efc-929ea661d5e9"
            }
    }
    @
    @POST_body_response
    {
        "session_token": "Ju4GMkL3vrjEAXVpAK38f3QBImlD8zQY"
    }
    @
    """

    @auth_router.post("/auth_qr_code/", name="auth_qr_login")
    async def post(
        self,
        request: Request,
        data: AuthQRCodeAuthorizationValidator,
        db: AsyncDatabaseAdapter = Depends(get_db_connection_for_submodule),
    ):
        data = data.model_dump()
        if data.get("qr_token"):
            session_token = await get_session_token_by_auxiliary(
                db, data.get("qr_token")
            )
            if not session_token:
                response = dict(message=_("There is no session token."))
                return JSONResponse(content=response, status_code=200)

            depended_services = (
                data.get("depended_services") if data.get("depended_services") else {}
            )
            for name, service_data in depended_services.items():
                depended_services_source = get_depended_services_source(request)
                try:
                    url = urljoin(
                        depended_services_source.get(name.lower()), "/get_session/"
                    )
                    async with httpx.AsyncClient() as client:
                        response_json = (
                            await client.post(url, json=service_data)
                        ).json()
                except Exception:
                    response_json = None
                if response_json:
                    session_token[name + "_session_token"] = response_json.get(
                        "session_token"
                    )
            response = dict(session_token)
            return JSONResponse(content=jsonable_encoder(response), status_code=200)
        else:
            return JSONResponse(content="QR token not found", status_code=400)


@cbv(auth_router)
class AuthSSOGenerationView:
    """
    @GET Allow to authenticate with Auth session@
    @GET_body_request
    Content-Type: None
    @
    @GET_body_response
    {
        "domain": "http://192.168.1.105:5000/auth_sso/",
        "service": "auth",
        "session": "Ng2YI6dovdBU5dgnFzfdlyvhN8e3Wh1m",
        "uuid": "1ac09e56-3f09-4f02-83ff-028b2a41a398"
    }
    @
    @POST Session generation on service based on request body@
    @POST_body_request
    {
        "service_uuid": "1ac09e56-3f09-4f02-83ff-028b2a41a398",
        "apt54": {
            "signature": "30450220121503996c58fd118fd065fc4c638ba235f00ddee8446c5",
            "user_data": {
                "root": true,
                "uuid": "66356f2e-987a-4031-af59-30a408f2fff5",
                "uinfo": {
                    "email": "qwerty@gmail.com",
                    "groups": ["4c97a2dc-c0df-4af0-a5c7-1753c46ca2e1"],
                    "password": "d8578edf8458ce06fbc5bb76a58c5ca4",
                    "last_name": "qwerty_pu",
                    "first_name": "qwerty_put"
                    },
                "created": "2022-04-21 09:09:59",
                "actor_type": "classic_user",
                "initial_key": "04a35e8a437a54d4826e83c3c476201a5259a3933a07cc3c6e056b5",
                "secondary_keys": null,
                "root_perms_signature": "30460221008241fd549d86047c709a18b43b6f1c1b67ba4c1192f2d"
                },
            "expiration": "2022-05-06 14:56:11"
            },
        "temporary_session": "f2K71OqINJkdYWDxOmDP7AEG12qtxv8e",
        "signature": "304602210087beb04a22e8dc294fcd618df319e5a9a2932fd0d0e1b"
    }
    @
    @POST_body_response
    {
        "message": "Session token was successfully created."
    }
    @
    """

    @auth_router.get("/auth_sso_generation/", name="auth-sso")
    async def get(
        self,
        request: Request,
        db: AsyncDatabaseAdapter = Depends(get_db_connection_for_submodule),
    ):
        base = await get_auth_domain(db, request)
        temporary_session = await create_temporary_session(db, request)
        domain = urljoin(base, "/auth_sso/")
        data = dict(
            domain=domain,
            session=temporary_session,
            uuid=request.app.config["SERVICE_UUID"],
            service=request.app.config.get("SERVICE_NAME", "").lower(),
        )
        return JSONResponse(content=data, status_code=200)

    @auth_router.post("/auth_sso_generation/", name="auth-sso")
    @service_only
    async def post(
        self,
        request: Request,
        data: dict,
        db: AsyncDatabaseAdapter = Depends(get_db_connection_for_submodule),
    ):
        signature = data.pop("signature", None)

        if not verify_signature(
            request.app.config["AUTH_PUB_KEY"],
            signature,
            json_dumps(data, sort_keys=True),
        ):
            logging_message(
                request,
                message="Signature verification. core.auth_view.AuthSSOView - POST.\n "
                "data - %s, signature - %s" % (data, signature),
            )
            response = create_response_message(
                message=_("Signature verification failed."), error=True
            )
            return JSONResponse(content=response, status_code=400)

        apt54 = data.get("apt54")
        if apt54:
            uuid = apt54["user_data"].get("uuid", None)
            if not uuid:
                logging_message(
                    request,
                    message="There is not uuid in APT54. core.auth_view.AuthSSOView - POST\n "
                    "apt54 - %s" % apt54,
                )
                response = create_response_message(
                    message=_(
                        "Invalid data in your authentication token. "
                        "Please try again or contact the administrator."
                    ),
                    error=True,
                )
                return JSONResponse(content=response, status_code=400)

        if not await actor_exists(db, uuid):
            # Add actor info in user_data key, cause create_actor function, creates user by apt54.
            actor = dict(user_data=data.get("actor"))
            if not await create_actor(request, db, actor):
                # Error while creating user
                logging_message(
                    request,
                    message="Error with creating actor. core.auth_view.AuthSSOView - POST.\n "
                    "actor - %s" % actor,
                )
                response = create_response_message(
                    message=_(
                        "Some error occurred while creating actor. "
                        "Please try again or contact the administrator."
                    ),
                    error=True,
                )
                return JSONResponse(content=response, status_code=400)

        if apt54:
            auxiliary_token = data.get("temporary_session")
            if auxiliary_token:
                response = await create_session_with_apt54(
                    apt54, request, db, auxiliary_token=auxiliary_token
                )
            if isinstance(response, dict) and response.get("error"):
                return JSONResponse(content=response, status_code=401)

            session_token = response
            if not session_token:
                logging_message(
                    request,
                    message="Error with creating session token. core.auth_view.AuthSSOView - POST.\n "
                    "error - %s" % response,
                )
                response = create_response_message(
                    message=_(
                        "Some error occurred while creating session token. "
                        "Please try again or contact the administrator."
                    ),
                    error=True,
                )
                return JSONResponse(content=response, status_code=400)

            response = create_response_message(
                message=_("Session token was successfully created.")
            )
        return JSONResponse(content=jsonable_encoder(response), status_code=200)


@cbv(auth_router)
class AuthSSOAuthorizationView:
    """
    @POST Get session token after back redirect from auth single sign on@
    @POST_body_request
    {
        "temporary_session": "f2K71OqINJkdYWDxOmDP7AEG12qtxv8e"
    }
    @
    @POST_body_response
    {
        "session_token": {
            "session_token": "VUHEI6Tdul9YCQ3fzHZEmhpByB3CZnMj"
        }
    }
    @
    """

    @auth_router.post("/auth_sso_login/", name="auth_sso_login")
    async def post(
        self,
        request: Request,
        db: AsyncDatabaseAdapter = Depends(get_db_connection_for_submodule),
    ):
        """
        Get session token after back redirect from auth single sign on.
        :param data: dict with salt from auth and signature.
        :return: message on response
        """
        try:
            data = await request.json()
        except (JSONDecodeError, UnicodeDecodeError):
            response = create_response_message(
                message=_("Invalid request type."), error=True
            )
            return JSONResponse(content=response, status_code=422)

        temporary_sessions = {
            key: value for key, value in data.items() if "temporary" in key
        }
        if temporary_sessions:
            if temporary_sessions.get("temporary_session"):
                temporary_session = temporary_sessions.pop("temporary_session")
                exists_result = await db.fetchone(
                    """SELECT EXISTS(SELECT 1 FROM temporary_session WHERE temporary_session = $1)""",
                    temporary_session,
                )
                exists = exists_result.get("exists") if exists_result else False
                if exists:
                    session_token = await get_session_token_by_auxiliary(
                        db, temporary_session
                    )
                    if session_token:
                        result = await db.fetchone(
                            """UPDATE service_session_token
                                SET auxiliary_token = NULL
                                WHERE auxiliary_token = $1
                                RETURNING apt54""",
                            temporary_session,
                        )
                        if not result or not (apt54 := result.get("apt54")):
                            raise Unauthorized(_("Actor have no session or APT54."))

                        session_token = dict(session_token)

                        await delete_temporary_session(
                            db, temporary_session=temporary_session, request=request
                        )

                        await BaseAuth.add_to_own_listing_group(
                            db,
                            request,
                            apt54["user_data"],
                        )
                    else:
                        session_token = dict()

                    for name, temporary_session in temporary_sessions.items():
                        service_name = name.replace("temporary_session_", "")
                        depended_services_source = get_depended_services_source(request)
                        async with httpx.AsyncClient() as client:
                            response_json = (
                                await client.post(
                                    depended_services_source.get(service_name)
                                    + "/get_session/",
                                    json={"temporary_session": temporary_session},
                                )
                            ).json()
                        if response_json:
                            session_token[service_name + "_session_token"] = (
                                response_json.get("session_token")
                            )
                    response = {"session_token": session_token}
                    return JSONResponse(content=response, status_code=200)
        return JSONResponse(
            content="Temporary session does not exists", status_code=400
        )


@cbv(auth_router)
class CreateSessionTokenByUuidView:
    """
    @POST Create session token by actor uuid. Admin only@
    @POST_body_request
    {
        "actor_uuid": "8e482f30-de28-4a5a-8e5e-4c525c72763d"
    }
    @
    @POST_body_response
    {
        "session_token": "2dfTUcgbyj2GGIUc2RuanS8jkxGO6Qni"
    }
    @
    """

    @auth_router.post("/create_session_by_uuid/", name="create_session_by_uuid")
    @admin_only
    async def post(
        self,
        request: Request,
        data: CreateSessionTokenByUuidValidator,
        db: AsyncDatabaseAdapter = Depends(get_db_connection_for_submodule),
    ):
        data = data.model_dump()
        try:
            session_token = await create_masquerading_session_token(
                db=db,
                request=request,
                actor_uuid=data.get("actor_uuid"),
                token_type="created_by_admin",
            )
        except ValueError as e:
            response, status_code = (
                create_response_message(message=e.args[0], error=True),
                400,
            )
        except ActorNotFound:
            response, status_code = (
                create_response_message(message="Actor not found", error=True),
                404,
            )
        else:
            response, status_code = {"session_token": session_token}, 200
        return JSONResponse(content=jsonable_encoder(response), status_code=status_code)


@cbv(auth_router)
class AboutView:
    """
    @GET Submodule Biom mode. Get page with json information about service and biom@
    @GET_body_request
    Content-Type: None
    @
    @GET_body_response
    {
        "auth_biom_public_key": "04cdd9c94a9ecbc7fd4a0c2582a6e8b514edbc26d6281fabbc02cdb",
        "biom_domain": "http://192.168.1.105:5000",
        "biom_name": null,
        "biom_uuid": "1ac09e56-3f09-4f02-83ff-028b2a41a398",
        "service_domain": "http://192.168.1.105:5002",
        "service_name": "Entity",
        "service_uuid": "db8972cd-c9e9-4cb9-9338-822209b71926"
    }
    @
    """

    @auth_router.get("/about/", name="about")
    async def get(
        self,
        request: Request,
        db: AsyncDatabaseAdapter = Depends(get_db_connection_for_submodule),
    ):
        query = """SELECT uuid AS uuid, uinfo->>'service_name' AS service_name,
                    uinfo->>'service_domain' AS service_domain FROM actor WHERE uuid = $1 AND actor_type = 'service'"""
        service_info = await db.fetchone(query, request.app.config["SERVICE_UUID"])

        if not service_info:
            logging_message(
                request,
                message="There is not service info. core.auth_view.AboutView - GET.",
            )
            response = create_response_message(
                message=_("Some error occurred while getting service info."), error=True
            )
            return JSONResponse(content=response, status_code=400)

        query = """SELECT uuid AS uuid, initial_key AS biom_public_key, uuid,
                    uinfo->>'biom_name' AS biom_name,
                    uinfo->>'service_domain' AS service_domain
                    FROM actor WHERE actor_type='service' AND initial_key=$1"""
        if request.app.config.get("AUTH_STANDALONE"):
            auth_info = await db.fetchone(
                query, request.app.config.get("SERVICE_PUBLIC_KEY")
            )
        else:
            auth_info = await db.fetchone(query, request.app.config.get("AUTH_PUB_KEY"))
        if not auth_info:
            logging_message(
                request,
                message="There is not biom info. core.auth_view.AboutView - GET.",
            )
            response = create_response_message(
                message=_("Some error occurred while getting service info."), error=True
            )
            return JSONResponse(content=response, status_code=400)

        response = dict(
            biom_uuid=auth_info.get("uuid"),
            biom_name=auth_info.get("biom_name", "Unknown"),
            auth_biom_public_key=auth_info.get("biom_public_key"),
            biom_domain=auth_info.get("service_domain", "Unknown"),
            service_uuid=service_info.get("uuid", "Unknown"),
            service_name=service_info.get("service_name", "Unknown"),
            service_domain=service_info.get("service_domain", "Unknown"),
        )

        return JSONResponse(content=jsonable_encoder(response), status_code=200)
