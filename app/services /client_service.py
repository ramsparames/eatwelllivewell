from app.database import (
    create_client,
    get_client,
    get_clients,
)


class ClientService:

    @staticmethod
    def list_clients():
        return get_clients()

    @staticmethod
    def get(client_id):
        return get_client(client_id)

    @staticmethod
    def create(
        name,
        email=None,
        phone=None,
        program="Transformation",
    ):
        return create_client(
            name=name,
            email=email,
            phone=phone,
            program=program,
        )
