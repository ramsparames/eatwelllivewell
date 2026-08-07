from app.database import (
    create_client,
    get_client,
    get_clients,
    create_weekly_checkin,
    get_client_checkins,
    get_calls_today,
    get_calls_this_week,
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
        @staticmethod
    def add_checkin(
        client_id,
