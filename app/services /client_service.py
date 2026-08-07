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
        call_date,
        weight_kg=None,
        stress_score=None,
        mood_score=None,
        next_call_date=None,
        next_call_time=None,
    ):
        return create_weekly_checkin(
            client_id=client_id,
            call_date=call_date,
            weight_kg=weight_kg,
            stress_score=stress_score,
            mood_score=mood_score,
            next_call_date=next_call_date,
            next_call_time=next_call_time,
        )

    @staticmethod
    def checkins(client_id):
        return get_client_checkins(client_id)

    @staticmethod
    def calls_today():
        return get_calls_today()

    @staticmethod
    def calls_this_week():
        return get_calls_this_week()
