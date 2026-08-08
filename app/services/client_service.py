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
    create_client_action,
    get_client_actions,
    complete_client_action,
    save_daily_tracking,
    get_client_tracking,
    save_client_intake,
    get_client_intake,
    save_client_measurement,
    get_client_measurements,
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
    next_call_date=None,
    next_call_time=None,
    wins=None,
    struggles=None,
    improvements_needed=None,
    coach_support=None,
):
    return create_weekly_checkin(
        client_id=client_id,
        call_date=call_date,
        weight_kg=weight_kg,
        next_call_date=next_call_date,
        next_call_time=next_call_time,
        wins=wins,
        struggles=struggles,
        improvements_needed=improvements_needed,
        coach_support=coach_support,
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
        active_actions = get_client_actions(
            client_id,
            status="active",
        )
        tracking = get_client_tracking(
            client_id
        )

        intake = get_client_intake(
            client_id
        )
        
        measurements = get_client_measurements(
            client_id
        )
        return {
            "client": client,
            "checkins": checkins,
            "active_actions": active_actions,
            "tracking": tracking,
            "current_week": current_week,
            "current_weight": current_weight,
            "weight_change": weight_change,
            "next_call_date": next_call_date,
            "next_call_time": next_call_time,
            "intake": intake,
            "measurements": measurements,
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
    
        
            client["weight_change"] = None
    
        return clients
    @staticmethod
    def add_action(
            client_id,
            action_name,
            target_count,
            target_unit,
            start_date,
            end_date=None,
            checkin_id=None,
    ):
        return create_client_action(
                client_id=client_id,
                action_name=action_name,
                target_count=target_count,
                target_unit=target_unit,
                start_date=start_date,
                end_date=end_date,
                checkin_id=checkin_id,
        )
        
    @staticmethod
    def actions(
        client_id,
        status=None,
    ):
        return get_client_actions(
            client_id,
            status=status,
        )
    
    
    @staticmethod
    def complete_action(
        action_id,
    ):
        complete_client_action(
            action_id
        )

    @staticmethod
    def save_tracking(
        client_id,
        tracked_on,
        protein=None,
        water=None,
        steps=None,
        strength_training=None,
        stress_score=None,
        mood_score=None,
        weight_kg=None,
        note=None,
    ):
        return save_daily_tracking(
            client_id=client_id,
            tracked_on=tracked_on,
            protein=protein,
            water=water,
            steps=steps,
            strength_training=strength_training,
            stress_score=stress_score,
            mood_score=mood_score,
            weight_kg=weight_kg,
            note=note,
        )
    
    
    @staticmethod
    def tracking(
        client_id,
        start_date=None,
        end_date=None,
    ):
        return get_client_tracking(
            client_id,
            start_date=start_date,
            end_date=end_date,
        )

@staticmethod
def save_intake(
    client_id,
    intake_date,
    current_situation=None,
    primary_goal=None,
    secondary_goals=None,
    goal_weight_kg=None,
    coach_focus=None,
):
    return save_client_intake(
        client_id=client_id,
        intake_date=intake_date,
        current_situation=current_situation,
        primary_goal=primary_goal,
        secondary_goals=secondary_goals,
        goal_weight_kg=goal_weight_kg,
        coach_focus=coach_focus,
    )


@staticmethod
def intake(client_id):
    return get_client_intake(
        client_id
    )


@staticmethod
def add_measurement(
    client_id,
    measured_on,
    weight_kg=None,
    upper_arm=None,
    chest=None,
    waist=None,
    lower_abdomen=None,
    hip=None,
    thigh=None,
    measurement_unit="inches",
    checkin_id=None,
):
    return save_client_measurement(
        client_id=client_id,
        measured_on=measured_on,
        weight_kg=weight_kg,
        upper_arm=upper_arm,
        chest=chest,
        waist=waist,
        lower_abdomen=lower_abdomen,
        hip=hip,
        thigh=thigh,
        measurement_unit=measurement_unit,
        checkin_id=checkin_id,
    )


@staticmethod
def measurements(client_id):
    return get_client_measurements(
        client_id
    )
