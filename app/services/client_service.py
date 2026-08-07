from datetime import date

from app.database import (
    create_client,
    get_client,
    get_clients,
    create_weekly_checkin,
    get_client_checkins,
    get_calls_today,
    get_calls_this_week,
    get_client_summaries,
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

    @staticmethod
    def profile(client_id):
        client = get_client(client_id)

        if not client:
            return None

        checkins = get_client_checkins(client_id)

        latest_checkin = (
            checkins[0]
            if checkins
            else None
        )

        current_weight = None
        next_call_date = None
        next_call_time = None

        if latest_checkin:
            current_weight = latest_checkin.get(
                "weight_kg"
            )

            next_call_date = latest_checkin.get(
                "next_call_date"
            )

            next_call_time = latest_checkin.get(
                "next_call_time"
            )

        start_date = client.get("start_date")

        current_week = None

        if start_date:
            days = (
                date.today() - start_date
            ).days

            if days >= 0:
                current_week = (
                    days // 7
                ) + 1

        initial_weight = client.get(
            "initial_weight_kg"
        )

        weight_change = None

        if (
            initial_weight is not None
            and current_weight is not None
        ):
            weight_change = (
                float(current_weight)
                - float(initial_weight)
            )

        return {
            "client": client,
            "checkins": checkins,
            "current_week": current_week,
            "current_weight": current_weight,
            "weight_change": weight_change,
            "next_call_date": next_call_date,
            "next_call_time": next_call_time,
        }
    @staticmethod
    def dashboard_clients():
        clients = get_client_summaries()
    
        today = date.today()
    
        for client in clients:
            start_date = client.get("start_date")
    
            if start_date:
                days = (today - start_date).days
    
                client["current_week"] = (
                    (days // 7) + 1
                    if days >= 0
                    else None
                )
            else:
                client["current_week"] = None
    
            initial_weight = client.get(
                "initial_weight_kg"
            )
    
            current_weight = client.get(
                "current_weight_kg"
            )
    
            if (
                initial_weight is not None
                and current_weight is not None
            ):
                client["weight_change"] = (
                    float(current_weight)
                    - float(initial_weight)
                )
            else:
                client["weight_change"] = None
    
        return clients
