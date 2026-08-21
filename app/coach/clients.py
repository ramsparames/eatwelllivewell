import os
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import coach_is_logged_in
from app.services.client_service import ClientService
from app.client.portal import router as client_portal_router
from app.services.phase_a_service import (
    RESOURCE_CATEGORIES,
    RESOURCE_TYPES,
    archive_resource,
    assign_resource,
    build_client_timeline,
    build_coach_summary,
    create_phase_a_tables,
    create_resource,
    get_client_resources,
    list_resources,
    unassign_resource,
)
from app.services.macro_tracking_service import (
    create_macro_tracking_tables,
    get_macro_history,
    get_macro_settings,
    save_macro_settings,
)

from app.services.action_identity_service import (
    ensure_action_identity_schema,
    new_custom_action_key,
    normalize_action_name,
    set_action_key,
)

from app.services.workout_service import (
    archive_workout,
    assign_workout,
    create_workout,
    create_workout_tables,
    get_client_workouts,
    get_workout_assignment_progress,
    list_workouts,
)

from app.services.coaching_insights_service import (
    get_client_weekly_summary,
    get_client_progress_charts,
)

from app.services.coaching_workflow_service import (
    create_coaching_workflow_tables,
    get_coach_weekly_feedback,
    get_weekly_reflection,
    save_coach_weekly_feedback,
    ensure_week_actions_carried_forward,
    replace_future_week_action_plan,
)

from app.services.client_portal_service import (
    ensure_portal_access,
    get_portal_access,
    get_recent_client_activity,
    get_coach_week_review,
    build_call_prep,
    get_next_client_call,
    get_client_operations_status,
    get_client_progress_summary,
    get_coach_history_grid,
)


router = APIRouter()

# Client-facing routes live in app/client/portal.py.
# Included here so no main.py change is required.
router.include_router(client_portal_router)

BASE_DIR = Path(__file__).resolve().parents[2]
templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates")
)

create_phase_a_tables()
create_workout_tables()
create_macro_tracking_tables()
create_coaching_workflow_tables()


ACTION_LIBRARY = [{'category': 'Nutrition',
  'levels': [{'level': 'Beginner',
              'items': [{'key': 'nutrition_beginner_protein_one_meal',
                         'name': 'Add protein to one meal',
                         'habit': 'Protein',
                         'target_unit': 'days'},
                        {'key': 'nutrition_beginner_protein_breakfast',
                         'name': 'Add protein to breakfast',
                         'habit': 'Protein',
                         'target_unit': 'days'},
                        {'key': 'nutrition_beginner_learn_protein_goal',
                         'name': 'Learn your daily protein goal',
                         'habit': 'Protein',
                         'target_unit': 'days'},
                        {'key': 'nutrition_beginner_vegetables_one_meal',
                         'name': 'Add vegetables to one meal',
                         'habit': 'Vegetables & Fibre',
                         'target_unit': 'days'},
                        {'key': 'nutrition_beginner_one_fruit',
                         'name': 'Eat one fruit daily',
                         'habit': 'Vegetables & Fibre',
                         'target_unit': 'days'},
                        {'key': 'nutrition_beginner_high_fibre_food',
                         'name': 'Add one high-fibre food (sprouts/beans/oats)',
                         'habit': 'Vegetables & Fibre',
                         'target_unit': 'days'},
                        {'key': 'nutrition_beginner_water_waking',
                         'name': 'Drink water after waking',
                         'habit': 'Hydration',
                         'target_unit': 'days'},
                        {'key': 'nutrition_beginner_carry_bottle',
                         'name': 'Carry a water bottle',
                         'habit': 'Hydration',
                         'target_unit': 'days'},
                        {'key': 'nutrition_beginner_water_15_2l',
                         'name': 'Meet 1.5–2 L water goal',
                         'habit': 'Hydration',
                         'target_unit': 'days'}]},
             {'level': 'Intermediate',
              'items': [{'key': 'nutrition_intermediate_protein_breakfast_lunch',
                         'name': 'Add protein to breakfast + lunch',
                         'habit': 'Protein',
                         'target_unit': 'days'},
                        {'key': 'nutrition_intermediate_protein_two_meals',
                         'name': 'Include protein in two meals consistently',
                         'habit': 'Protein',
                         'target_unit': 'days'},
                        {'key': 'nutrition_intermediate_vegetables_two_meals',
                         'name': 'Add vegetables to two meals',
                         'habit': 'Vegetables & Fibre',
                         'target_unit': 'days'},
                        {'key': 'nutrition_intermediate_half_lunch_vegetables',
                         'name': 'Fill half your lunch plate with vegetables',
                         'habit': 'Vegetables & Fibre',
                         'target_unit': 'days'},
                        {'key': 'nutrition_intermediate_two_fruits',
                         'name': 'Eat 2 fruits/day',
                         'habit': 'Vegetables & Fibre',
                         'target_unit': 'days'},
                        {'key': 'nutrition_intermediate_seeds',
                         'name': 'Add seeds (chia/flax/pumpkin)',
                         'habit': 'Vegetables & Fibre',
                         'target_unit': 'days'},
                        {'key': 'nutrition_intermediate_drink_before_meal',
                         'name': 'Drink before every meal',
                         'habit': 'Hydration',
                         'target_unit': 'days'},
                        {'key': 'nutrition_intermediate_personal_water',
                         'name': 'Meet personalized water goal',
                         'habit': 'Hydration',
                         'target_unit': 'days'}]},
             {'level': 'Advanced',
              'items': [{'key': 'nutrition_advanced_protein_three_meals',
                         'name': 'Include protein in all 3 meals',
                         'habit': 'Protein',
                         'target_unit': 'days'},
                        {'key': 'nutrition_advanced_protein_target',
                         'name': 'Meet personalized protein target daily',
                         'habit': 'Protein',
                         'target_unit': 'days'},
                        {'key': 'nutrition_advanced_prep_protein',
                         'name': 'Prep protein for tomorrow',
                         'habit': 'Protein',
                         'target_unit': 'days'},
                        {'key': 'nutrition_advanced_veg_servings',
                         'name': 'Eat 3–5 servings vegetables/day',
                         'habit': 'Vegetables & Fibre',
                         'target_unit': 'days'},
                        {'key': 'nutrition_advanced_rainbow',
                         'name': 'Eat a rainbow of vegetables weekly',
                         'habit': 'Vegetables & Fibre',
                         'target_unit': 'days'},
                        {'key': 'nutrition_advanced_fermented',
                         'name': 'Include fermented foods',
                         'habit': 'Vegetables & Fibre',
                         'target_unit': 'days'},
                        {'key': 'nutrition_advanced_plan_tomorrow',
                         'name': 'Plan meals for tomorrow',
                         'habit': 'Nutrition Habits',
                         'target_unit': 'days'},
                        {'key': 'nutrition_advanced_meal_prep',
                         'name': 'Meal prep for the week',
                         'habit': 'Nutrition Habits',
                         'target_unit': 'times'},
                        {'key': 'nutrition_advanced_slow_mindful',
                         'name': 'Eat slowly and mindfully',
                         'habit': 'Nutrition Habits',
                         'target_unit': 'days'}]}]},
 {'category': 'Movement',
  'levels': [{'level': 'Beginner',
              'items': [{'key': 'movement_beginner_walk_10',
                         'name': 'Walk 10 minutes',
                         'habit': 'Walking',
                         'target_unit': 'days'},
                        {'key': 'movement_beginner_5000_steps',
                         'name': 'Reach 5,000 steps',
                         'habit': 'Steps',
                         'target_unit': 'days'},
                        {'key': 'movement_beginner_stretch_5',
                         'name': 'Stretch 5 minutes',
                         'habit': 'Mobility',
                         'target_unit': 'days'},
                        {'key': 'movement_beginner_strength_one',
                         'name': 'Complete one strength workout/week',
                         'habit': 'Strength',
                         'target_unit': 'sessions'}]},
             {'level': 'Intermediate',
              'items': [{'key': 'movement_intermediate_walk_after_meal',
                         'name': 'Walk after one meal',
                         'habit': 'Walking',
                         'target_unit': 'days'},
                        {'key': 'movement_intermediate_7500_steps',
                         'name': 'Reach 7,500 steps',
                         'habit': 'Steps',
                         'target_unit': 'days'},
                        {'key': 'movement_intermediate_stretch_10',
                         'name': 'Stretch 10 minutes',
                         'habit': 'Mobility',
                         'target_unit': 'days'},
                        {'key': 'movement_intermediate_strength_two',
                         'name': 'Complete two strength workouts/week',
                         'habit': 'Strength',
                         'target_unit': 'sessions'},
                        {'key': 'movement_intermediate_mobility',
                         'name': 'Practice mobility routine',
                         'habit': 'Mobility',
                         'target_unit': 'sessions'}]},
             {'level': 'Advanced',
              'items': [{'key': 'movement_advanced_step_goal',
                         'name': 'Reach personalized step goal',
                         'habit': 'Steps',
                         'target_unit': 'days'},
                        {'key': 'movement_advanced_walk_two_meals',
                         'name': 'Walk after two meals',
                         'habit': 'Walking',
                         'target_unit': 'days'},
                        {'key': 'movement_advanced_strength_three',
                         'name': 'Complete three strength workouts/week',
                         'habit': 'Strength',
                         'target_unit': 'sessions'},
                        {'key': 'movement_advanced_progressive_overload',
                         'name': 'Progressive overload',
                         'habit': 'Strength',
                         'target_unit': 'sessions'},
                        {'key': 'movement_advanced_recovery_walk',
                         'name': 'Recovery walk',
                         'habit': 'Recovery',
                         'target_unit': 'sessions'},
                        {'key': 'movement_advanced_yoga_mobility',
                         'name': 'Yoga or mobility session',
                         'habit': 'Mobility',
                         'target_unit': 'sessions'}]}]},
 {'category': 'Sleep',
  'levels': [{'level': 'Beginner',
              'items': [{'key': 'sleep_beginner_fixed_bedtime',
                         'name': 'Fixed bedtime',
                         'habit': 'Sleep Routine',
                         'target_unit': 'days'},
                        {'key': 'sleep_beginner_fixed_wakeup',
                         'name': 'Fixed wake-up time',
                         'habit': 'Sleep Routine',
                         'target_unit': 'days'},
                        {'key': 'sleep_beginner_no_screens',
                         'name': 'No screens 30 minutes before bed',
                         'habit': 'Sleep Routine',
                         'target_unit': 'days'},
                        {'key': 'sleep_beginner_morning_sunlight',
                         'name': 'Morning sunlight (10 minutes)',
                         'habit': 'Sleep Routine',
                         'target_unit': 'days'},
                        {'key': 'sleep_beginner_box_breathing',
                         'name': 'Box Breathing',
                         'habit': 'Breathing',
                         'target_unit': 'sessions'},
                        {'key': 'sleep_beginner_478',
                         'name': '4-7-8 Breathing',
                         'habit': 'Breathing',
                         'target_unit': 'sessions'}]},
             {'level': 'Intermediate',
              'items': [{'key': 'sleep_intermediate_bedtime_routine',
                         'name': 'Bedtime routine',
                         'habit': 'Sleep Routine',
                         'target_unit': 'days'},
                        {'key': 'sleep_intermediate_read',
                         'name': 'Read before bed',
                         'habit': 'Sleep Routine',
                         'target_unit': 'days'},
                        {'key': 'sleep_intermediate_stretch',
                         'name': 'Stretch before bed',
                         'habit': 'Sleep Routine',
                         'target_unit': 'days'},
                        {'key': 'sleep_intermediate_cool_dark',
                         'name': 'Cool & dark bedroom',
                         'habit': 'Sleep Environment',
                         'target_unit': 'days'},
                        {'key': 'sleep_intermediate_left_nostril',
                         'name': 'Left Nostril Breathing',
                         'habit': 'Breathing',
                         'target_unit': 'sessions'},
                        {'key': 'sleep_intermediate_diaphragmatic',
                         'name': 'Diaphragmatic Breathing',
                         'habit': 'Breathing',
                         'target_unit': 'sessions'},
                        {'key': 'sleep_intermediate_alternate_nostril',
                         'name': 'Alternate Nostril Breathing',
                         'habit': 'Breathing',
                         'target_unit': 'sessions'}]},
             {'level': 'Advanced',
              'items': [{'key': 'sleep_advanced_7_8_hours',
                         'name': 'Sleep 7–8 hours consistently',
                         'habit': 'Sleep Routine',
                         'target_unit': 'days'},
                        {'key': 'sleep_advanced_consistent_schedule',
                         'name': 'Consistent sleep schedule',
                         'habit': 'Sleep Routine',
                         'target_unit': 'days'},
                        {'key': 'sleep_advanced_journal',
                         'name': 'Journal before bed',
                         'habit': 'Relaxation',
                         'target_unit': 'days'},
                        {'key': 'sleep_advanced_track_quality',
                         'name': 'Track sleep quality',
                         'habit': 'Sleep Tracking',
                         'target_unit': 'days'},
                        {'key': 'sleep_advanced_pmr',
                         'name': 'Progressive Muscle Relaxation',
                         'habit': 'Relaxation',
                         'target_unit': 'sessions'},
                        {'key': 'sleep_advanced_yoga_nidra',
                         'name': 'Yoga Nidra',
                         'habit': 'Relaxation',
                         'target_unit': 'sessions'},
                        {'key': 'sleep_advanced_guided_meditation',
                         'name': 'Guided Sleep Meditation',
                         'habit': 'Relaxation',
                         'target_unit': 'sessions'}]}]},
 {'category': 'Stress',
  'levels': [{'level': 'Beginner',
              'items': [{'key': 'stress_beginner_gratitude',
                         'name': 'Practice gratitude',
                         'habit': 'Stress Management',
                         'target_unit': 'days'},
                        {'key': 'stress_beginner_5_breaths',
                         'name': 'Take 5 deep breaths',
                         'habit': 'Breathing',
                         'target_unit': 'sessions'},
                        {'key': 'stress_beginner_outside',
                         'name': 'Spend 10 minutes outside',
                         'habit': 'Stress Management',
                         'target_unit': 'days'},
                        {'key': 'stress_beginner_music',
                         'name': 'Listen to calming music',
                         'habit': 'Stress Management',
                         'target_unit': 'days'}]},
             {'level': 'Intermediate',
              'items': [{'key': 'stress_intermediate_meditation',
                         'name': 'Meditation (5–10 min)',
                         'habit': 'Meditation',
                         'target_unit': 'sessions'},
                        {'key': 'stress_intermediate_journal',
                         'name': 'Journal emotions',
                         'habit': 'Journaling',
                         'target_unit': 'days'},
                        {'key': 'stress_intermediate_plan_tomorrow',
                         'name': 'Plan tomorrow',
                         'habit': 'Planning',
                         'target_unit': 'days'},
                        {'key': 'stress_intermediate_declutter',
                         'name': 'Declutter one space',
                         'habit': 'Environment',
                         'target_unit': 'times'},
                        {'key': 'stress_intermediate_self_compassion',
                         'name': 'Practice self-compassion',
                         'habit': 'Mindset',
                         'target_unit': 'days'}]},
             {'level': 'Advanced',
              'items': [{'key': 'stress_advanced_body_scan',
                         'name': 'Body scan meditation',
                         'habit': 'Meditation',
                         'target_unit': 'sessions'},
                        {'key': 'stress_advanced_progressive_relaxation',
                         'name': 'Progressive relaxation',
                         'habit': 'Relaxation',
                         'target_unit': 'sessions'},
                        {'key': 'stress_advanced_downtime',
                         'name': 'Schedule intentional downtime',
                         'habit': 'Recovery',
                         'target_unit': 'sessions'},
                        {'key': 'stress_advanced_digital_detox',
                         'name': 'Digital detox',
                         'habit': 'Recovery',
                         'target_unit': 'sessions'},
                        {'key': 'stress_advanced_nature_walk',
                         'name': 'Nature walk',
                         'habit': 'Recovery',
                         'target_unit': 'sessions'},
                        {'key': 'stress_advanced_weekly_wins',
                         'name': 'Reflect on weekly wins',
                         'habit': 'Reflection',
                         'target_unit': 'times'}]}]},
 {'category': 'Energy',
  'levels': [{'level': 'Beginner',
              'items': [{'key': 'energy_beginner_breakfast',
                         'name': 'Eat breakfast',
                         'habit': 'Fuel',
                         'target_unit': 'days'},
                        {'key': 'energy_beginner_water',
                         'name': 'Drink water after waking',
                         'habit': 'Hydration',
                         'target_unit': 'days'},
                        {'key': 'energy_beginner_sunlight',
                         'name': 'Morning sunlight',
                         'habit': 'Circadian Rhythm',
                         'target_unit': 'days'},
                        {'key': 'energy_beginner_supplements',
                         'name': 'Take prescribed supplements',
                         'habit': 'Health Routine',
                         'target_unit': 'days'},
                        {'key': 'energy_beginner_afternoon_walk',
                         'name': 'Take a short afternoon walk',
                         'habit': 'Movement',
                         'target_unit': 'days'}]},
             {'level': 'Intermediate',
              'items': [{'key': 'energy_intermediate_protein_first',
                         'name': 'Protein in first meal',
                         'habit': 'Fuel',
                         'target_unit': 'days'},
                        {'key': 'energy_intermediate_balance_meals',
                         'name': 'Balance meals throughout the day',
                         'habit': 'Fuel',
                         'target_unit': 'days'},
                        {'key': 'energy_intermediate_reduce_crash',
                         'name': 'Reduce afternoon energy crashes',
                         'habit': 'Energy Rhythm',
                         'target_unit': 'days'},
                        {'key': 'energy_intermediate_no_skip',
                         'name': 'Avoid skipping meals',
                         'habit': 'Fuel',
                         'target_unit': 'days'},
                        {'key': 'energy_intermediate_move_hourly',
                         'name': 'Move every hour',
                         'habit': 'Movement',
                         'target_unit': 'days'}]},
             {'level': 'Advanced',
              'items': [{'key': 'energy_advanced_stable_energy',
                         'name': 'Maintain stable energy throughout the day',
                         'habit': 'Energy Rhythm',
                         'target_unit': 'days'},
                        {'key': 'energy_advanced_busy_days',
                         'name': 'Pre-plan busy days',
                         'habit': 'Planning',
                         'target_unit': 'days'},
                        {'key': 'energy_advanced_fuel_workouts',
                         'name': 'Fuel workouts properly',
                         'habit': 'Fuel',
                         'target_unit': 'days'},
                        {'key': 'energy_advanced_meal_timing',
                         'name': 'Maintain consistent meal timing',
                         'habit': 'Fuel',
                         'target_unit': 'days'},
                        {'key': 'energy_advanced_track_energy',
                         'name': 'Track energy daily',
                         'habit': 'Tracking',
                         'target_unit': 'days'}]}]},
 {'category': 'Connection',
  'levels': [{'level': 'Beginner',
              'items': [{'key': 'connection_beginner_call_friend',
                         'name': 'Call a friend',
                         'habit': 'Social Connection',
                         'target_unit': 'times'},
                        {'key': 'connection_beginner_family_meal',
                         'name': 'Eat one meal with family',
                         'habit': 'Family',
                         'target_unit': 'days'},
                        {'key': 'connection_beginner_share_win',
                         'name': 'Share one win',
                         'habit': 'Support',
                         'target_unit': 'times'},
                        {'key': 'connection_beginner_ask_help',
                         'name': 'Ask for help when needed',
                         'habit': 'Support',
                         'target_unit': 'times'}]},
             {'level': 'Intermediate',
              'items': [{'key': 'connection_intermediate_family_time',
                         'name': 'Spend quality time with family',
                         'habit': 'Family',
                         'target_unit': 'sessions'},
                        {'key': 'connection_intermediate_listening',
                         'name': 'Practice active listening',
                         'habit': 'Communication',
                         'target_unit': 'days'},
                        {'key': 'connection_intermediate_coaching_call',
                         'name': 'Join the weekly coaching call',
                         'habit': 'Coaching',
                         'target_unit': 'sessions'},
                        {'key': 'connection_intermediate_accountability',
                         'name': 'Check in with your accountability partner',
                         'habit': 'Accountability',
                         'target_unit': 'times'}]},
             {'level': 'Advanced',
              'items': [{'key': 'connection_advanced_mentor',
                         'name': 'Mentor someone',
                         'habit': 'Community',
                         'target_unit': 'times'},
                        {'key': 'connection_advanced_gratitude',
                         'name': 'Express gratitude to someone',
                         'habit': 'Connection',
                         'target_unit': 'times'},
                        {'key': 'connection_advanced_community',
                         'name': 'Participate in the NourisHer community',
                         'habit': 'Community',
                         'target_unit': 'sessions'},
                        {'key': 'connection_advanced_celebrate',
                         'name': "Celebrate another person's success",
                         'habit': 'Connection',
                         'target_unit': 'times'},
                        {'key': 'connection_advanced_ritual',
                         'name': 'Build a meaningful weekly connection ritual',
                         'habit': 'Connection',
                         'target_unit': 'sessions'}]}]}]

ACTION_LIBRARY_BY_KEY = {
    item["key"]: item
    for category in ACTION_LIBRARY
    for level in category["levels"]
    for item in level["items"]
}

ensure_action_identity_schema(ACTION_LIBRARY_BY_KEY)


def _safe_target_count(value: str | None) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if 1 <= parsed <= 7 else None


def _selected_library_assignments(
    selected_action_keys: list[str],
    all_action_keys: list[str],
    target_counts: list[str],
    target_units: list[str],
):
    """
    The form submits target controls for every visible library action.
    Only rows whose key is present in selected_action_keys are assigned.
    This means target/unit controls can remain clickable without JavaScript.
    """
    selected = set(selected_action_keys)
    assignments = []

    for index, action_key in enumerate(all_action_keys):
        if action_key not in selected:
            continue

        library_action = ACTION_LIBRARY_BY_KEY.get(action_key)
        if not library_action:
            continue

        count = _safe_target_count(
            target_counts[index] if index < len(target_counts) else ""
        )
        if count is None:
            continue

        unit = (
            target_units[index].strip()
            if index < len(target_units) and target_units[index].strip()
            else library_action.get("target_unit", "days")
        )
        if unit not in {"days", "sessions", "times"}:
            unit = library_action.get("target_unit", "days")

        assignments.append(
            {
                "name": library_action["name"],
                "action_key": action_key,
                "target_count": count,
                "target_unit": unit,
            }
        )

    return assignments



def _custom_action_assignments(
    names: list[str],
    target_counts: list[str],
    target_units: list[str],
    action_keys: list[str] | None = None,
):
    assignments = []
    for index, raw_name in enumerate(names):
        name = (raw_name or "").strip()
        if not name:
            continue

        count = _safe_target_count(
            target_counts[index] if index < len(target_counts) else ""
        )
        if count is None:
            continue

        unit = (
            target_units[index].strip()
            if index < len(target_units) and target_units[index].strip()
            else "days"
        )
        if unit not in {"days", "sessions", "times"}:
            unit = "days"

        supplied_key = (
            action_keys[index].strip()
            if action_keys and index < len(action_keys) and action_keys[index].strip()
            else ""
        )
        assignments.append(
            {
                "name": name,
                "action_key": supplied_key or new_custom_action_key(),
                "target_count": count,
                "target_unit": unit,
            }
        )
    return assignments


def _normalize_action_name(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


ACTION_LIBRARY_KEY_BY_NORMALIZED_NAME = {
    _normalize_action_name(item["name"]): key
    for key, item in ACTION_LIBRARY_BY_KEY.items()
}


CALL_TIME_SLOTS = [
    {
        "value": f"{hour:02d}:{minute:02d}",
        "label": (
            f"{12 if hour % 12 == 0 else hour % 12}:{minute:02d} "
            f"{'AM' if hour < 12 else 'PM'}"
        ),
    }
    for hour in range(6, 23)
    for minute in (0, 30)
    if not (hour == 22 and minute == 30)
]


def _coaching_week_bounds(client: dict, on_date: date | None = None):
    """Return Week N and its real 7-day boundaries from clients.start_date."""
    on_date = on_date or date.today()
    start_date = client.get("start_date")

    if not start_date:
        return 0, None, None

    if on_date < start_date:
        return 1, start_date, start_date + timedelta(days=6)

    elapsed = (on_date - start_date).days
    week_number = (elapsed // 7) + 1
    week_start = start_date + timedelta(days=(week_number - 1) * 7)
    return week_number, week_start, week_start + timedelta(days=6)


def _action_week_bounds(client_id: int, on_date: date):
    client = ClientService.get(client_id) or {}
    _, week_start, week_end = _coaching_week_bounds(client, on_date)
    if week_start is None:
        week_start = on_date
        week_end = on_date + timedelta(days=6)
    return week_start, week_end




def _add_action_with_identity(
    *,
    client_id: int,
    assignment: dict,
    start_date,
    end_date,
    checkin_id=None,
):
    ClientService.add_action(
        client_id=client_id,
        action_name=assignment["name"],
        target_count=assignment["target_count"],
        target_unit=assignment["target_unit"],
        start_date=start_date,
        end_date=end_date,
        checkin_id=checkin_id,
    )
    set_action_key(
        client_id=client_id,
        action_name=assignment["name"],
        start_date=start_date,
        end_date=end_date,
        action_key=assignment["action_key"],
    )


def _build_synamate_booking_url(
    base_url: str,
    client: dict,
) -> str:
    """
    Add NourisHer client identity to the Synamate public booking URL.

    Synamate's public help center documents the contact fields used by the
    calendar/contact system but does not publish a formal booking-URL query
    parameter contract. We therefore send the common contact field names in
    both full-name and split-name form. Existing query parameters are kept.
    """
    base_url = (base_url or "").strip()
    if not base_url:
        return ""

    full_name = (client.get("name") or "").strip()
    email = (client.get("email") or "").strip()
    phone = (client.get("phone") or "").strip()

    name_parts = full_name.split(maxsplit=1)
    first_name = name_parts[0] if name_parts else ""
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    parts = urlsplit(base_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))

    # Use setdefault so an intentionally configured value in the base URL wins.
    if full_name:
        query.setdefault("name", full_name)
        query.setdefault("full_name", full_name)
    if first_name:
        query.setdefault("first_name", first_name)
    if last_name:
        query.setdefault("last_name", last_name)
    if email:
        query.setdefault("email", email)
    if phone:
        query.setdefault("phone", phone)

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment,
        )
    )


@router.get(
    "/dashboard/clients",
    response_class=HTMLResponse,
)
def clients_page(request: Request):
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    clients = ClientService.dashboard_clients()
    calls_today = ClientService.calls_today()
    calls_this_week = ClientService.calls_this_week()

    today = date.today()

    for client in clients:
        checkins = ClientService.checkins(
            client["id"]
        )

        latest_checkin = (
            checkins[0]
            if checkins
            else None
        )

        week_number, week_start, week_end = _coaching_week_bounds(
            client,
            today,
        )
        client["current_week"] = week_number
        client["current_week_start"] = week_start
        client["current_week_end"] = week_end

        client["last_checkin_date"] = (
            latest_checkin.get("call_date")
            if latest_checkin
            else None
        )

        # Keep weight fallback from the latest weekly review.
        if latest_checkin and client.get("current_weight_kg") is None:
            client["current_weight_kg"] = latest_checkin.get("weight_kg")

        # Synamate is now the single source of truth for the next coaching call.
        # Populate the legacy display keys too so the existing Clients template
        # can show the synced appointment without needing a markup change.
        synced_call = get_next_client_call(client)

        client["next_synced_call"] = synced_call
        client["next_call_date"] = None
        client["next_call_time"] = None

        if synced_call and synced_call.get("local_start_time"):
            local_start = synced_call["local_start_time"]
            client["next_call_date"] = local_start.date()
            client["next_call_time"] = local_start.time().replace(tzinfo=None)
            client["next_call_source"] = "synamate"
        else:
            client["next_call_source"] = None

        ops = get_client_operations_status(client, today)
        client["operations"] = ops
        client["health_key"] = ops["health_key"]
        client["health_label"] = ops["health_label"]

        # Values used by the browser-side table sorter.
        client["sort_name"] = (
            client.get("name")
            or ""
        ).lower()

        client["sort_week"] = (
            client.get("current_week")
            or 0
        )

        client["sort_next_call"] = (
            client["next_synced_call"]["local_start_time"].isoformat()
            if (
                client.get("next_synced_call")
                and client["next_synced_call"].get("local_start_time")
            )
            else "9999-12-31T23:59:59"
        )

        client["sort_last_checkin"] = (
            client.get(
                "last_checkin_date"
            ).isoformat()
            if client.get(
                "last_checkin_date"
            )
            else "0000-00-00"
        )

    active_clients = [
        client
        for client in clients
        if client.get("status") == "active"
    ]

    needs_attention = [
        client
        for client in active_clients
        if client.get("health_key")
        == "attention"
    ]

    return templates.TemplateResponse(
        "coach/clients.html",
        {
            "request": request,
            "active_nav": "clients",
            "clients": clients,
            "active_clients": active_clients,
            "calls_today": calls_today,
            "calls_this_week": calls_this_week,
            "needs_attention": needs_attention,
        },
    )


@router.post("/dashboard/clients")
def add_client(
    request: Request,
    name: str = Form(...),
    email: str = Form(""),
    country_code: str = Form("+91"),
    phone: str = Form(""),
    program: str = Form("Transformation"),
):
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    clean_phone = phone.strip()
    if clean_phone and not clean_phone.startswith("+"):
        clean_phone = f"{country_code.strip()} {clean_phone}".strip()

    client_id = ClientService.create(
        name=name.strip(),
        email=email.strip() or None,
        phone=clean_phone or None,
        program=program,
    )

    return RedirectResponse(
        f"/dashboard/clients/{client_id}",
        status_code=303,
    )


@router.post(
    "/dashboard/clients/{client_id}/portal-access"
)
def create_client_portal_access(
    request: Request,
    client_id: int,
):
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    ensure_portal_access(client_id)

    return RedirectResponse(
        f"/dashboard/clients/{client_id}",
        status_code=303,
    )


@router.get(
    "/dashboard/clients/{client_id}",
    response_class=HTMLResponse,
)
def client_profile(
    request: Request,
    client_id: int,
):
    if not coach_is_logged_in(request):
        return RedirectResponse("/coach/login", status_code=303)

    profile = ClientService.profile(client_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Client not found")

    if profile.get("current_weight") is None and profile.get("measurements"):
        latest_measurement = profile["measurements"][0]
        if latest_measurement.get("weight_kg") is not None:
            profile["current_weight"] = latest_measurement.get("weight_kg")

    week_number, week_start, week_end = _coaching_week_bounds(
        profile["client"],
        date.today(),
    )
    profile["current_week"] = week_number
    profile["current_week_start"] = week_start
    profile["current_week_end"] = week_end

    if week_start and week_end:
        ensure_week_actions_carried_forward(
            client_id,
            week_start,
            week_end,
        )

    # Weekly Check-in can browse the client's coaching history using the
    # exact same week boundaries as the Client Portal.
    requested_week = request.query_params.get("week")
    try:
        coach_week_number = int(requested_week) if requested_week else week_number
    except (TypeError, ValueError):
        coach_week_number = week_number

    coach_week_number = max(1, min(coach_week_number, week_number + 1))

    client_start_date = profile["client"].get("start_date")
    if client_start_date:
        coach_week_start = client_start_date + timedelta(
            days=(coach_week_number - 1) * 7
        )
        coach_week_end = coach_week_start + timedelta(days=6)
    else:
        coach_week_start = week_start
        coach_week_end = week_end

    coach_week_is_current = coach_week_number == week_number
    coach_week_is_past = coach_week_number < week_number
    coach_week_is_future = coach_week_number > week_number

    for entry in profile.get("tracking") or []:
        if entry.get("weight_kg") is not None:
            profile["current_weight"] = entry.get("weight_kg")
            break

    portal_access = get_portal_access(client_id)
    portal_activity = get_recent_client_activity(client_id, limit=14)

    week_review = None
    call_prep = None
    progress_summary = None
    next_week_number = None
    next_week_start = None
    next_week_end = None
    next_week_actions = []

    if week_start and week_end:
        # Overview remains anchored to the real current week.
        progress_summary = get_client_progress_summary(
            client_id,
            week_start,
            week_number,
            weeks=4,
        )

        # Weekly Check-in follows the week selected by the coach.
        week_review = get_coach_week_review(
            client_id,
            coach_week_start,
            coach_week_end,
        )
        call_prep = build_call_prep(
            client_id,
            coach_week_start,
            coach_week_end,
        )

        # Next-week planning is only actionable from the current week.
        next_week_number = week_number + 1
        next_week_start = week_end + timedelta(days=1)
        next_week_end = next_week_start + timedelta(days=6)
        next_week_actions = ClientService.actions(
            client_id,
            status="active",
            start_date=next_week_start,
            end_date=next_week_end,
        )

    coach_history_grid = get_coach_history_grid(
        client_id,
        on_date=date.today(),
    )
    macro_settings = get_macro_settings(client_id)
    macro_history = get_macro_history(
        client_id,
        profile["client"].get("start_date"),
        date.today(),
    )
    if coach_history_grid and macro_settings.get("enabled"):
        for row in coach_history_grid.get("rows") or []:
            row["macro"] = macro_history["by_date"].get(row["date"])

    # Coaching intelligence for the current client workspace.
    # These are computed before TemplateResponse so the Jinja context never
    # references undefined variables.
    coaching_week_summary = get_client_weekly_summary(
        client_id,
        week_start=week_start,
    )
    progress_charts = get_client_progress_charts(
        client_id,
        weeks=12,
    )

    client_weekly_reflection = get_weekly_reflection(
        client_id,
        coach_week_start,
    )
    coach_weekly_feedback = get_coach_weekly_feedback(
        client_id,
        coach_week_start,
    )

    # Preselect every currently ACTIVE commitment for next week.
    #
    # Actions can be created at different times (especially custom actions),
    # so they must not be grouped by one shared start_date/checkin.
    # ClientService.actions() returns newest rows first. Keep only the newest
    # active record for each action name, then classify it as library/custom.
    carry_forward_action_defaults = {}
    carry_forward_custom_actions = []

    if coach_week_is_current:
        library_key_by_name = ACTION_LIBRARY_KEY_BY_NORMALIZED_NAME

        active_rows = ClientService.actions(
            client_id,
            status="active",
        ) or []

        latest_by_name = {}

        for row in active_rows:
            name = (row.get("action_name") or "").strip()
            if not name:
                continue

            # Rows are returned newest first, so the first occurrence wins.
            if name in latest_by_name:
                continue

            latest_by_name[name] = row

        for name, action in latest_by_name.items():
            stable_key = (action.get("action_key") or "").strip()
            default = {
                "name": name,
                "action_key": stable_key,
                "target_count": action.get("target_count"),
                "target_unit": action.get("target_unit") or "days",
            }

            library_key = (
                stable_key
                if stable_key in ACTION_LIBRARY_BY_KEY
                else library_key_by_name.get(_normalize_action_name(name))
            )

            if library_key:
                carry_forward_action_defaults[library_key] = default
            else:
                carry_forward_custom_actions.append(default)

    # Keep enough custom rows for all carried-forward custom actions plus
    # a few blank rows for additions during the coaching call.
    custom_action_slot_count = max(
        5,
        len(carry_forward_custom_actions) + 3,
    )

    client_resources = get_client_resources(client_id)
    available_resources = list_resources()
    client_workouts = get_client_workouts(client_id)
    available_workouts = list_workouts()
    client_timeline = build_client_timeline(profile["client"])
    coach_summary = build_coach_summary(call_prep, progress_summary)

    next_synced_call = get_next_client_call(profile["client"])
    coaching_booking_base_url = os.getenv(
        "SYNAMATE_COACHING_CALL_URL",
        "",
    ).strip()
    coaching_booking_url = _build_synamate_booking_url(
        coaching_booking_base_url,
        profile["client"],
    )

    return templates.TemplateResponse(
        "coach/client_workspace.html",
        {
            "request": request,
            "active_nav": "clients",
            "action_library": ACTION_LIBRARY,
            "call_time_slots": CALL_TIME_SLOTS,
            "portal_access": portal_access,
            "portal_activity": portal_activity,
            "week_review": week_review,
            "call_prep": call_prep,
            "coach_week_number": coach_week_number,
            "coach_week_start": coach_week_start,
            "coach_week_end": coach_week_end,
            "coach_week_is_current": coach_week_is_current,
            "coach_week_is_past": coach_week_is_past,
            "coach_week_is_future": coach_week_is_future,
            "coach_week_can_previous": coach_week_number > 1,
            "coach_week_can_next": coach_week_number < week_number + 1,
            "progress_summary": progress_summary,
            "coach_summary": coach_summary,
            "coach_history_grid": coach_history_grid,
            "coaching_week_summary": coaching_week_summary,
            "progress_charts": progress_charts,
            "client_weekly_reflection": client_weekly_reflection,
            "coach_weekly_feedback": coach_weekly_feedback,
            "macro_settings": macro_settings,
            "macro_history": macro_history,
            "client_timeline": client_timeline,
            "client_resources": client_resources,
            "available_resources": available_resources,
            "client_workouts": client_workouts,
            "available_workouts": available_workouts,
            "resource_categories": RESOURCE_CATEGORIES,
            "resource_types": RESOURCE_TYPES,
            "next_synced_call": next_synced_call,
            "coaching_booking_url": coaching_booking_url,
            "next_week_number": next_week_number,
            "next_week_start": next_week_start,
            "next_week_end": next_week_end,
            "next_week_action_names": {
                row.get("action_name") for row in next_week_actions
            },
            "carry_forward_action_defaults": carry_forward_action_defaults,
            "carry_forward_custom_actions": carry_forward_custom_actions,
            "custom_action_slot_count": custom_action_slot_count,
            **profile,
        },
    )



@router.get(
    "/dashboard/resources",
    response_class=HTMLResponse,
)
def resource_library_page(request: Request):
    if not coach_is_logged_in(request):
        return RedirectResponse("/coach/login", status_code=303)

    return templates.TemplateResponse(
        "coach/resource_library.html",
        {
            "request": request,
            "active_nav": "clients",
            "resources": list_resources(active_only=False),
            "workouts": list_workouts(active_only=False),
            "clients": ClientService.dashboard_clients(),
            "resource_types": RESOURCE_TYPES,
            "resource_categories": RESOURCE_CATEGORIES,
        },
    )


@router.post("/dashboard/workouts")
def add_workout(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    category: str = Form("Strength"),
    duration_minutes: str = Form(""),
    equipment: str = Form(""),
    exercise_titles: list[str] = Form(default=[]),
    exercise_video_urls: list[str] = Form(default=[]),
    exercise_sets: list[str] = Form(default=[]),
    exercise_reps: list[str] = Form(default=[]),
    exercise_rest_seconds: list[str] = Form(default=[]),
    exercise_instructions: list[str] = Form(default=[]),
):
    if not coach_is_logged_in(request):
        return RedirectResponse("/coach/login", status_code=303)

    exercises = []
    for i, name in enumerate(exercise_titles):
        name = name.strip()
        if not name:
            continue
        exercises.append({
            "title": name,
            "video_url": exercise_video_urls[i] if i < len(exercise_video_urls) else "",
            "sets": exercise_sets[i] if i < len(exercise_sets) else "3",
            "reps_text": exercise_reps[i] if i < len(exercise_reps) else "",
            "rest_seconds": exercise_rest_seconds[i] if i < len(exercise_rest_seconds) else "",
            "instructions": exercise_instructions[i] if i < len(exercise_instructions) else "",
        })

    if not exercises:
        raise HTTPException(status_code=400, detail="Add at least one exercise")

    create_workout(
        title=title.strip(),
        description=description.strip() or None,
        category=category.strip() or "Strength",
        duration_minutes=int(duration_minutes) if duration_minutes.strip() else None,
        equipment=equipment.strip() or None,
        exercises=exercises,
    )
    return RedirectResponse("/dashboard/resources?workout_added=1", status_code=303)


@router.post("/dashboard/workouts/{workout_id}/assign")
def assign_workout_route(
    request: Request,
    workout_id: int,
    client_ids: list[int] = Form(default=[]),
    coach_note: str = Form(""),
):
    if not coach_is_logged_in(request):
        return RedirectResponse("/coach/login", status_code=303)
    if not client_ids:
        return RedirectResponse("/dashboard/resources?assign_error=clients", status_code=303)

    assign_workout(
        workout_id=workout_id,
        client_ids=client_ids,
        coach_note=coach_note.strip() or None,
    )
    return RedirectResponse("/dashboard/resources?workout_assigned=1", status_code=303)


@router.post("/dashboard/workouts/{workout_id}/archive")
def archive_workout_route(request: Request, workout_id: int):
    if not coach_is_logged_in(request):
        return RedirectResponse("/coach/login", status_code=303)
    archive_workout(workout_id)
    return RedirectResponse("/dashboard/resources", status_code=303)


@router.get(
    "/dashboard/clients/{client_id}/workouts/{assignment_id}",
    response_class=HTMLResponse,
)
def coach_client_workout_detail(
    request: Request,
    client_id: int,
    assignment_id: int,
):
    if not coach_is_logged_in(request):
        return RedirectResponse("/coach/login", status_code=303)

    profile = ClientService.profile(client_id)
    workout = get_workout_assignment_progress(assignment_id, client_id)

    if not profile or not workout:
        raise HTTPException(status_code=404, detail="Workout assignment not found")

    return templates.TemplateResponse(
        "coach/workout_detail.html",
        {
            "request": request,
            "client": profile["client"],
            "workout": workout,
        },
    )


@router.post("/dashboard/clients/{client_id}/workouts")
def assign_client_workout_route(
    request: Request,
    client_id: int,
    workout_id: int = Form(...),
    coach_note: str = Form(""),
):
    if not coach_is_logged_in(request):
        return RedirectResponse("/coach/login", status_code=303)
    assign_workout(
        workout_id=workout_id,
        client_ids=[client_id],
        coach_note=coach_note.strip() or None,
    )
    return RedirectResponse(
        f"/dashboard/clients/{client_id}?tab=resources",
        status_code=303,
    )


@router.post("/dashboard/resources")
def add_resource(
    request: Request,
    title: str = Form(...),
    resource_type: str = Form("video"),
    category: str = Form("Other"),
    description: str = Form(""),
    resource_url: str = Form(...),
    duration_minutes: str = Form(""),
):
    if not coach_is_logged_in(request):
        return RedirectResponse("/coach/login", status_code=303)

    duration = (
        int(duration_minutes)
        if duration_minutes.strip()
        else None
    )

    create_resource(
        title=title.strip(),
        resource_type=resource_type,
        category=category,
        description=description.strip() or None,
        resource_url=resource_url.strip(),
        duration_minutes=duration,
    )

    return RedirectResponse(
        "/dashboard/resources?added=1",
        status_code=303,
    )


@router.post("/dashboard/resources/{resource_id}/archive")
def archive_resource_route(
    request: Request,
    resource_id: int,
):
    if not coach_is_logged_in(request):
        return RedirectResponse("/coach/login", status_code=303)

    archive_resource(resource_id)
    return RedirectResponse("/dashboard/resources", status_code=303)


@router.post("/dashboard/clients/{client_id}/resources")
def assign_client_resource(
    request: Request,
    client_id: int,
    resource_id: int = Form(...),
    coach_note: str = Form(""),
):
    if not coach_is_logged_in(request):
        return RedirectResponse("/coach/login", status_code=303)

    assign_resource(
        client_id=client_id,
        resource_id=resource_id,
        coach_note=coach_note.strip() or None,
    )

    return RedirectResponse(
        f"/dashboard/clients/{client_id}?tab=resources",
        status_code=303,
    )


@router.post(
    "/dashboard/clients/{client_id}/resources/{assignment_id}/remove"
)
def remove_client_resource(
    request: Request,
    client_id: int,
    assignment_id: int,
):
    if not coach_is_logged_in(request):
        return RedirectResponse("/coach/login", status_code=303)

    unassign_resource(client_id, assignment_id)

    return RedirectResponse(
        f"/dashboard/clients/{client_id}?tab=resources",
        status_code=303,
    )


@router.post(
    "/dashboard/clients/{client_id}/intake"
)
def save_client_intake_route(
    request: Request,
    client_id: int,
    intake_date: str = Form(...),
    phone: str = Form(""),
    week_start_date: str = Form(...),
    current_situation: str = Form(""),
    primary_goal: str = Form(""),
    secondary_goals: str = Form(""),
    present_weight_kg: str = Form(""),
    goal_weight_kg: str = Form(""),
    coach_focus: str = Form(""),
    action_keys: list[str] = Form(default=[]),
    action_all_keys: list[str] = Form(default=[]),
    action_target_counts: list[str] = Form(default=[]),
    action_target_units: list[str] = Form(default=[]),
    custom_action_names: list[str] = Form(default=[]),
    custom_action_keys: list[str] = Form(default=[]),
    custom_target_counts: list[str] = Form(default=[]),
    custom_target_units: list[str] = Form(default=[]),
    macro_tracking_enabled: str = Form(""),
    macro_protein_target_g: str = Form(""),
    macro_carbs_target_g: str = Form(""),
    macro_fat_target_g: str = Form(""),
):
    if not coach_is_logged_in(request):
        return RedirectResponse("/coach/login", status_code=303)

    parsed_present_weight = (
        float(present_weight_kg) if present_weight_kg.strip() else None
    )
    parsed_goal_weight = (
        float(goal_weight_kg) if goal_weight_kg.strip() else None
    )
    parsed_week_start = date.fromisoformat(week_start_date)

    ClientService.set_phone(client_id, phone.strip() or None)
    ClientService.save_intake(
        client_id=client_id,
        intake_date=intake_date,
        current_situation=current_situation.strip() or None,
        primary_goal=primary_goal.strip() or None,
        secondary_goals=secondary_goals.strip() or None,
        goal_weight_kg=parsed_goal_weight,
        coach_focus=coach_focus.strip() or None,
    )
    ClientService.set_start_date(client_id, parsed_week_start)

    def _optional_float(value: str):
        return float(value) if value and value.strip() else None

    save_macro_settings(
        client_id=client_id,
        enabled=(macro_tracking_enabled == "1"),
        protein_target_g=_optional_float(macro_protein_target_g),
        carbs_target_g=_optional_float(macro_carbs_target_g),
        fat_target_g=_optional_float(macro_fat_target_g),
    )

    if parsed_present_weight is not None:
        ClientService.add_measurement(
            client_id=client_id,
            measured_on=intake_date,
            weight_kg=parsed_present_weight,
            measurement_unit="cm",
            checkin_id=None,
        )

    first_week_end = parsed_week_start + timedelta(days=6)
    added_names = set()

    assignments = _selected_library_assignments(
        action_keys,
        action_all_keys,
        action_target_counts,
        action_target_units,
    )
    assignments.extend(
        _custom_action_assignments(
            custom_action_names,
            custom_target_counts,
            custom_target_units,
            custom_action_keys,
        )
    )

    for assignment in assignments:
        if assignment["name"] in added_names:
            continue
        _add_action_with_identity(
            client_id=client_id,
            assignment=assignment,
            start_date=parsed_week_start,
            end_date=first_week_end,
        )
        added_names.add(assignment["name"])

    return RedirectResponse(
        f"/dashboard/clients/{client_id}",
        status_code=303,
    )


@router.post("/dashboard/clients/{client_id}/macro-settings")
def update_client_macro_settings(
    request: Request,
    client_id: int,
    macro_tracking_enabled: str = Form(""),
    macro_protein_target_g: str = Form(""),
    macro_carbs_target_g: str = Form(""),
    macro_fat_target_g: str = Form(""),
):
    if not coach_is_logged_in(request):
        return RedirectResponse("/coach/login", status_code=303)

    def optional_float(value: str):
        return float(value) if value and value.strip() else None

    save_macro_settings(
        client_id=client_id,
        enabled=(macro_tracking_enabled == "1"),
        protein_target_g=optional_float(macro_protein_target_g),
        carbs_target_g=optional_float(macro_carbs_target_g),
        fat_target_g=optional_float(macro_fat_target_g),
    )
    return RedirectResponse(
        f"/dashboard/clients/{client_id}?tab=clientdata&macro_saved=1",
        status_code=303,
    )


@router.post(
    "/dashboard/clients/{client_id}/week-start"
)
def save_week_start(
    request: Request,
    client_id: int,
    week_start_date: str = Form(...),
):
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    parsed = date.fromisoformat(week_start_date)
    ClientService.set_start_date(client_id, parsed)

    return RedirectResponse(
        f"/dashboard/clients/{client_id}",
        status_code=303,
    )


@router.post(
    "/dashboard/clients/{client_id}/actions"
)
def add_client_action(
    request: Request,
    client_id: int,
    action_key: str = Form(""),
    target_count: str = Form(""),
    target_unit: str = Form("days"),
    custom_action_name: str = Form(""),
    custom_target_count: str = Form(""),
    custom_target_unit: str = Form(""),
):
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    action_name = None
    action_identity_key = None
    target_count = None
    target_unit = None

    if action_key:
        library_action = ACTION_LIBRARY_BY_KEY.get(action_key)
        if library_action:
            action_name = library_action["name"]
            action_identity_key = action_key
            target_count = _safe_target_count(target_count)
            target_unit = (
                target_unit.strip()
                if target_unit.strip() in {"days", "sessions", "times"}
                else library_action.get("target_unit", "days")
            )

    if not action_name and custom_action_name.strip():
        action_name = custom_action_name.strip()
        action_identity_key = new_custom_action_key()
        target_count = (
            int(custom_target_count)
            if custom_target_count.strip()
            else None
        )
        target_unit = custom_target_unit.strip() or None

    if action_name:
        existing_names = {
            row.get("action_name")
            for row in ClientService.actions(client_id, status="active")
        }

        if action_name not in existing_names:
            start_date, end_date = _action_week_bounds(
                client_id,
                date.today(),
            )
            _add_action_with_identity(
                client_id=client_id,
                assignment={
                    "name": action_name,
                    "action_key": action_identity_key,
                    "target_count": target_count,
                    "target_unit": target_unit,
                },
                start_date=start_date,
                end_date=end_date,
            )

    return RedirectResponse(
        f"/dashboard/clients/{client_id}",
        status_code=303,
    )


@router.post(
    "/dashboard/clients/{client_id}/tracking"
)
def save_client_tracking(
    request: Request,
    client_id: int,
    tracked_on: str = Form(...),
    protein: bool = Form(False),
    water: bool = Form(False),
    steps: str = Form(""),
    strength_training: bool = Form(False),
    stress_score: str = Form(""),
    mood_score: str = Form(""),
    weight_kg: str = Form(""),
    note: str = Form(""),
):
    if not coach_is_logged_in(request):
        return RedirectResponse(
            "/coach/login",
            status_code=303,
        )

    parsed_steps = (
        int(steps)
        if steps.strip()
        else None
    )

    parsed_stress = (
        int(stress_score)
        if stress_score.strip()
        else None
    )

    parsed_mood = (
        int(mood_score)
        if mood_score.strip()
        else None
    )

    parsed_weight = (
        float(weight_kg)
        if weight_kg.strip()
        else None
    )

    ClientService.save_tracking(
        client_id=client_id,
        tracked_on=tracked_on,
        protein=protein,
        water=water,
        steps=parsed_steps,
        strength_training=strength_training,
        stress_score=parsed_stress,
        mood_score=parsed_mood,
        weight_kg=None,
        note=note.strip() or None,
    )

    return RedirectResponse(
        f"/dashboard/clients/{client_id}",
        status_code=303,
    )


@router.post(
    "/dashboard/clients/{client_id}/checkin"
)
def add_client_checkin(
    request: Request,
    client_id: int,
    call_date: str = Form(...),
    wins: str = Form(""),
    struggles: str = Form(""),
    improvements_needed: str = Form(""),
    coach_support: str = Form(""),
    action_keys: list[str] = Form(default=[]),
    action_all_keys: list[str] = Form(default=[]),
    action_target_counts: list[str] = Form(default=[]),
    action_target_units: list[str] = Form(default=[]),
    custom_action_names: list[str] = Form(default=[]),
    custom_action_keys: list[str] = Form(default=[]),
    custom_target_counts: list[str] = Form(default=[]),
    custom_target_units: list[str] = Form(default=[]),
    workout_ids: list[int] = Form(default=[]),
    weekly_client_feedback: str = Form(""),
    weekly_private_note: str = Form(""),
):
    if not coach_is_logged_in(request):
        return RedirectResponse("/coach/login", status_code=303)

    checkin_id = ClientService.add_checkin(
        client_id=client_id,
        call_date=call_date,
        weight_kg=None,
        next_call_date=None,
        next_call_time=None,
        wins=wins.strip() or None,
        struggles=struggles.strip() or None,
        improvements_needed=improvements_needed.strip() or None,
        coach_support=coach_support.strip() or None,
    )

    client = ClientService.get(client_id) or {}
    _, _, current_week_end = _coaching_week_bounds(
        client,
        date.fromisoformat(call_date),
    )
    if current_week_end is None:
        current_week_end = date.fromisoformat(call_date)

    action_start_date = current_week_end + timedelta(days=1)
    action_end_date = action_start_date + timedelta(days=6)

    assignments = _selected_library_assignments(
        action_keys,
        action_all_keys,
        action_target_counts,
        action_target_units,
    )
    assignments.extend(
        _custom_action_assignments(
            custom_action_names,
            custom_target_counts,
            custom_target_units,
            custom_action_keys,
        )
    )

    # Sushma's saved plan is the exception to the standing plan.
    # Rebuild this unstarted upcoming week from exactly what she selected.
    replace_future_week_action_plan(
        client_id,
        action_start_date,
        action_end_date,
    )

    existing_action_names = set()
    for assignment in assignments:
        if assignment["name"] in existing_action_names:
            continue
        _add_action_with_identity(
            client_id=client_id,
            assignment=assignment,
            start_date=action_start_date,
            end_date=action_end_date,
            checkin_id=checkin_id,
        )
        existing_action_names.add(assignment["name"])

    save_coach_weekly_feedback(
        client_id=client_id,
        week_start=current_week_end - timedelta(days=6),
        client_feedback=weekly_client_feedback.strip() or None,
        private_note=weekly_private_note.strip() or None,
        checkin_id=checkin_id,
    )

    for workout_id in workout_ids:
        assign_workout(
            workout_id=workout_id,
            client_ids=[client_id],
            coach_note=None,
            planned_week_start=action_start_date,
        )

    return RedirectResponse(
        f"/dashboard/clients/{client_id}?tab=weekly",
        status_code=303,
    )
