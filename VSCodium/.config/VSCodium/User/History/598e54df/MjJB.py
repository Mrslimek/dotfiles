from typing import Optional
import os
import uuid
from getpass import getpass

from typer import Option
from typing_extensions import Annotated
from email_validator import validate_email as email_validator_function, EmailNotValidError


from .base import BaseCommand
from ..exceptions import DatabaseError
from ...core.ecdsa_lib import sign_data, generate_key_pair
from ...core.utils import hash_md5, json_dumps


class CreateRootUser(BaseCommand):
    def __init__(self, settings=None, manager=None):
        super().__init__(settings, manager)

    def run(
        self,
        first_name: Annotated[Optional[str], Option("--first_name", "-fn", help="First name")] = None,
        last_name: Annotated[Optional[str], Option("--last_name", "-ln", help="Last name")] = None,
        email: Annotated[Optional[str], Option("--email", "-e", help="Email address")] = None,
        password: Annotated[Optional[str], Option("--password", "-p", help="Password")] = None
    ):
        """
        Create root user for standalone mode
        """
        if not self.__check_table_exists():
            print("\033[93mBefore creating root user, you should apply migrations.\033[0m")
            return

        # if not os.getuid() == 0 and os.name == 'posix':  # Only check on POSIX systems
        #     print("\033[93mYou should use this command from root only!\033[0m")
        #     return

        if first_name is None:
            first_name = input("First Name:")
        if last_name is None:
            last_name = input("Last Name:")
        if email is None:
            email = input("Email address:")

        try:
            email_validator_function(email)
        except EmailNotValidError as e:
            print(f"\033[91m{str(e)}\033[0m")
            return

        # Check if user with such email already exists using the manager's database connection
        with self.get_db_cursor() as cur:
            cur.execute("""SELECT EXISTS(SELECT 1 FROM actor WHERE uinfo ->> 'email' = %s)""", [email])
            result = cur.fetchone()
            if result and result[0]:  # The first column of the first row (PostgreSQL returns as tuples)
                print("\033[91mUser with such email already exists.\033[0m")
                return

        if password is None:
            password = getpass("Password:")
            password_confirm = getpass("Password confirm:")

            if password != password_confirm:
                print("\033[91mPasswords didn't match.\033[0m")
                return

        uinfo = {
            "email": email,
            # FIXME: For some reason psycopg2 here returns tuple, so to get uuid we assume that uuid is always first element
            "groups": [self.get_default_user_group()[0]],
            "password": hash_md5(password),
            "last_name": last_name,
            "first_name": first_name,
        }

        root_uuid = uuid.uuid4()
        private_key, public_key = generate_key_pair()

        # Get service private key from settings
        service_private_key = self._get_config_value("SERVICE_PRIVATE_KEY")

        root_signature = sign_data(service_private_key, root_uuid.__str__() + public_key)

        actor = {
            "initial_key": public_key,
            "root_perms_signature": root_signature,
            "actor_type": "classic_user",
            "uinfo": uinfo,
            "uuid": root_uuid,
        }

        values = [json_dumps(actor)]
        query = """INSERT INTO actor (SELECT * FROM jsonb_populate_record(null::actor, %s::jsonb)) RETURNING uuid"""

        try:
            with self.get_db_cursor() as cur:
                cur.execute(query, values)
                actor_uuid = cur.fetchone()
        except Exception as e:
            print(f"\033[91m{e}\033[0m")
            return

        print(f'\033[92mRoot user {actor_uuid[0] if actor_uuid else "unknown"} successfully created.\033[0m')

    def __check_table_exists(self):
        table_name = "actor"
        with self.get_db_cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = %s", (table_name,))
            result = cur.fetchone()

        if result and result[0] == 1:  # The first column of the first row
            return True
        return False

    # NOTE: Duplicate of utils method from core.utils
    def get_default_user_group(self):
        """
        Get default user group. By default user adds in this group
        :return: group
        @subm_flow
        """
        with self.get_db_cursor() as cur:
            cur.execute(
                """SELECT * FROM actor WHERE actor_type='group' AND uinfo->>'group_name'=%s""",
                [self._get_config_value("DEFAULT_GROUP_NAME", "DEFAULT")],
            )
            group = cur.fetchone()
            if group is None:
                raise DatabaseError("Group is None. Are you sure you have necessary groups in actor table?")
        return group
