import os
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import coach_is_logged_in
from app.database import get_connection
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
    get_weekly_reflection,
)

from app.services.client_portal_service import (
    create_portal_tables,
    ensure_portal_access,
    get_portal_access,
    get_client_by_token,
    get_recent_client_activity,
    get_coach_week_review,
    build_call_prep,
    get_next_client_call,
    get_client_operations_status,
    get_client_progress_summary,
    get_coach_history_grid,
    save_client_question,
    get_client_questions,
    mark_client_question_answered,
)


from app.services.client_nudge_service import (
    get_latest_client_nudges,
    nudge_is_recent,
)

from app.services.coaching_call_workflow_service import (
    create_coaching_call_tables,
    get_call_notes,
    get_latest_call_note,
    get_workflow_timeline,
    save_call_note,
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
create_coaching_call_tables()
create_portal_tables()


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




def _program_length_weeks(client: dict) -> int | None:
    """Best available program length, so the final week has no fake next week."""
    for key in ("program_weeks", "duration_weeks", "total_weeks"):
        value = client.get(key)
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = 0
        if parsed > 0:
            return parsed

    start_date = client.get("start_date")
    for key in ("program_end_date", "end_date"):
        end_date = client.get(key)
        if start_date and end_date:
            try:
                return max(1, ((end_date - start_date).days // 7) + 1)
            except Exception:
                pass

    # Current NourisHer program defaults. These only apply when the database
    # does not already carry an explicit duration/end date.
    program = (client.get("program") or "").strip().lower()
    if "foundation" in program:
        return 12
    if "transformation" in program or "nourisher" in program:
        return 26
    return None


def _week_action_defaults(rows: list[dict] | None):
    """Split saved week actions into library defaults and custom actions."""
    library_defaults = {}
    custom_defaults = []
    latest_by_name = {}

    for raw in rows or []:
        row = dict(raw)
        name = (row.get("action_name") or "").strip()
        if not name or name in latest_by_name:
            continue
        latest_by_name[name] = row

    for name, row in latest_by_name.items():
        stable_key = (row.get("action_key") or "").strip()
        default = {
            "name": name,
            "action_key": stable_key,
            "target_count": row.get("target_count"),
            "target_unit": row.get("target_unit") or "days",
        }
        library_key = (
            stable_key
            if stable_key in ACTION_LIBRARY_BY_KEY
            else ACTION_LIBRARY_KEY_BY_NORMALIZED_NAME.get(
                _normalize_action_name(name)
            )
        )
        if library_key:
            default["action_key"] = library_key
            library_defaults[library_key] = default
        else:
            custom_defaults.append(default)

    return library_defaults, custom_defaults


def _replace_week_actions(
    *,
    client_id: int,
    week_start: date,
    week_end: date,
    assignments: list[dict],
    checkin_id: int | None = None,
):
    """
    Make the selected week exactly match the submitted commitments.

    Existing rows are updated in place whenever possible so any daily logs
    already attached to the assignment stay intact. Removed current-week
    commitments are ended before today; future/past correction rows without
    logs can be deleted safely.
    """
    desired = {}
    for assignment in assignments:
        key = (assignment.get("action_key") or "").strip()
        identity = f"key:{key}" if key else (
            "name:" + _normalize_action_name(assignment.get("name"))
        )
        desired[identity] = assignment

    with get_connection() as connection:
        with connection.cursor() as cursor:
            # Only rows that BELONG to this exact coaching week may be
            # edited/reused. Older standing rows must never be moved forward,
            # because doing that rewrites historical Week 1/2 commitments.
            cursor.execute(
                """
                SELECT *
                FROM client_action_plans
                WHERE client_id = %s
                  AND start_date = %s
                  AND (end_date = %s OR end_date IS NULL)
                ORDER BY id DESC
                """,
                (client_id, week_start, week_end),
            )
            existing_rows = [dict(row) for row in cursor.fetchall()]

            cursor.execute(
                """SELECT EXISTS (
                       SELECT 1
                       FROM information_schema.columns
                       WHERE table_name='client_action_plans'
                         AND column_name='action_key'
                   ) AS yes"""
            )
            has_action_key = bool(cursor.fetchone()["yes"])

            existing_by_identity = {}
            for row in existing_rows:
                stable_key = (row.get("action_key") or "").strip()
                library_key = (
                    stable_key
                    if stable_key in ACTION_LIBRARY_BY_KEY
                    else ACTION_LIBRARY_KEY_BY_NORMALIZED_NAME.get(
                        _normalize_action_name(row.get("action_name"))
                    )
                )
                # Stable identity wins for BOTH library and custom actions.
                # Previously custom:* keys were discarded here and custom rows
                # were matched by name instead. That caused edits to create
                # duplicate rows and removed custom actions to reappear.
                identity = (
                    f"key:{stable_key}"
                    if stable_key
                    else (
                        f"key:{library_key}"
                        if library_key
                        else "name:" + _normalize_action_name(row.get("action_name"))
                    )
                )
                existing_by_identity.setdefault(identity, row)

            # Close legacy/open-ended plans from PRIOR weeks at the boundary
            # of the selected week. This keeps history immutable while making
            # the selected week's explicit plan authoritative.
            cursor.execute(
                """
                UPDATE client_action_plans
                SET end_date = %s
                WHERE client_id = %s
                  AND start_date < %s
                  AND (end_date IS NULL OR end_date >= %s)
                """,
                (week_start - timedelta(days=1), client_id, week_start, week_start),
            )

            kept_ids = set()
            for identity, assignment in desired.items():
                row = existing_by_identity.get(identity)
                if row:
                    kept_ids.add(row["id"])
                    if has_action_key:
                        cursor.execute(
                            """
                            UPDATE client_action_plans
                            SET action_name=%s,
                                action_key=%s,
                                target_count=%s,
                                target_unit=%s,
                                start_date=%s,
                                end_date=%s,
                                status='active',
                                checkin_id=COALESCE(%s, checkin_id)
                            WHERE id=%s
                            """,
                            (
                                assignment["name"],
                                assignment.get("action_key") or None,
                                assignment.get("target_count"),
                                assignment.get("target_unit"),
                                week_start,
                                week_end,
                                checkin_id,
                                row["id"],
                            ),
                        )
                    else:
                        cursor.execute(
                            """
                            UPDATE client_action_plans
                            SET action_name=%s,
                                target_count=%s,
                                target_unit=%s,
                                start_date=%s,
                                end_date=%s,
                                status='active',
                                checkin_id=COALESCE(%s, checkin_id)
                            WHERE id=%s
                            """,
                            (
                                assignment["name"],
                                assignment.get("target_count"),
                                assignment.get("target_unit"),
                                week_start,
                                week_end,
                                checkin_id,
                                row["id"],
                            ),
                        )
                    continue

                if has_action_key:
                    cursor.execute(
                        """
                        INSERT INTO client_action_plans
                        (client_id, checkin_id, action_name, action_key,
                         target_count, target_unit, start_date, end_date, status)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'active')
                        """,
                        (
                            client_id,
                            checkin_id,
                            assignment["name"],
                            assignment.get("action_key") or None,
                            assignment.get("target_count"),
                            assignment.get("target_unit"),
                            week_start,
                            week_end,
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO client_action_plans
                        (client_id, checkin_id, action_name,
                         target_count, target_unit, start_date, end_date, status)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,'active')
                        """,
                        (
                            client_id,
                            checkin_id,
                            assignment["name"],
                            assignment.get("target_count"),
                            assignment.get("target_unit"),
                            week_start,
                            week_end,
                        ),
                    )

            # Remove commitments no longer selected. Preserve already-entered
            # daily history by shortening the assignment instead of deleting it.
            for row in existing_rows:
                if row["id"] in kept_ids:
                    continue

                cursor.execute(
                    """
                    SELECT COUNT(*) AS n
                    FROM client_action_daily_logs
                    WHERE action_id=%s
                    """,
                    (row["id"],),
                )
                has_logs = (cursor.fetchone()["n"] or 0) > 0

                if has_logs:
                    cutoff = min(date.today() - timedelta(days=1), week_end)
                    if cutoff >= week_start:
                        cursor.execute(
                            """
                            UPDATE client_action_plans
                            SET end_date=%s, status='completed'
                            WHERE id=%s
                            """,
                            (cutoff, row["id"]),
                        )
                    else:
                        cursor.execute(
                            "UPDATE client_action_plans SET status='completed' WHERE id=%s",
                            (row["id"],),
                        )
                else:
                    cursor.execute(
                        "DELETE FROM client_action_plans WHERE id=%s",
                        (row["id"],),
                    )


def _active_exact_week_actions(
    client_id: int,
    week_start: date,
    week_end: date,
) -> list[dict]:
    """
    Return the exact active plan currently saved for one coaching week.

    Weekly Coaching uses this for form defaults so removed/completed historical
    rows (which the Data history may still retain) do not reappear in the
    editable commitment builder.
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    action_name,
                    action_key,
                    target_count,
                    target_unit,
                    start_date,
                    end_date,
                    status,
                    checkin_id
                FROM client_action_plans
                WHERE client_id = %s
                  AND start_date = %s
                  AND end_date = %s
                  AND status = 'active'
                ORDER BY id
                """,
                (client_id, week_start, week_end),
            )
            return [dict(row) for row in (cursor.fetchall() or [])]


def _submitted_assignments(
    *,
    selected_keys: list[str],
    all_keys: list[str],
    target_counts: list[str],
    target_units: list[str],
    custom_names: list[str],
    custom_keys: list[str],
    custom_counts: list[str],
    custom_units: list[str],
):
    assignments = _selected_library_assignments(
        selected_keys,
        all_keys,
        target_counts,
        target_units,
    )
    assignments.extend(
        _custom_action_assignments(
            custom_names,
            custom_counts,
            custom_units,
            custom_keys,
        )
    )
    return assignments


@router.post("/client/{access_token}/questions")
def submit_client_question(
    access_token: str,
    question_text: str = Form(""),
):
    client = get_client_by_token(access_token)
    if not client:
        raise HTTPException(status_code=404, detail="Client portal not found")

    clean_question = (question_text or "").strip()
    if not clean_question:
        return RedirectResponse(
            f"/client/{access_token}?question_error=1#ask-sushma",
            status_code=303,
        )

    week_number, _, _ = _coaching_week_bounds(
        dict(client),
        date.today(),
    )

    try:
        save_client_question(
            client_id=client["id"],
            question_text=clean_question,
            week_number=week_number or None,
        )
    except ValueError:
        return RedirectResponse(
            f"/client/{access_token}?question_error=1#ask-sushma",
            status_code=303,
        )

    return RedirectResponse(
        f"/client/{access_token}?question_saved=1#ask-sushma",
        status_code=303,
    )


@router.post(
    "/dashboard/clients/{client_id}/questions/{question_id}/answered"
)
def answer_client_question(
    request: Request,
    client_id: int,
    question_id: int,
):
    if not coach_is_logged_in(request):
        return RedirectResponse("/coach/login", status_code=303)

    mark_client_question_answered(client_id, question_id)
    return RedirectResponse(
        f"/dashboard/clients/{client_id}#client-questions",
        status_code=303,
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
    latest_nudges = get_latest_client_nudges([client["id"] for client in clients])

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

        # Keep the full operations payload available to the workspace, but
        # simplify the Clients screen status so it matches the main dashboard.
        coaching_signals = ops.get("coaching_signals") or {}

        client["operations"] = ops

        # The client list has four simple states:
        # - setup
        # - needs follow-up
        # - ready for review
        # - on track
        #
        # No-next-call, measurement due, or workouts behind remain useful
        # information, but do not make the whole client row red.
        if not client.get("start_date"):
            client["health_key"] = "setup"
            client["health_label"] = "Setup"

        elif (
            (ops.get("missed_daily_count") or 0) >= 2
            or coaching_signals.get("low_adherence")
        ):
            client["health_key"] = "attention"
            client["health_label"] = "Needs follow-up"

        elif ops.get("weekly_review_overdue"):
            client["health_key"] = "review"
            client["health_label"] = "Ready for review"

        else:
            client["health_key"] = "on_track"
            client["health_label"] = "On track"

        # Build one short client-row note. This is informational and does not
        # affect the health state.
        client["client_status_note"] = None

        if client["health_key"] == "attention":
            if (ops.get("missed_daily_count") or 0) >= 2:
                missed = ops.get("missed_daily_count") or 0
                client["client_status_note"] = (
                    f"No tracking for {missed} day"
                    + ("s" if missed != 1 else "")
                )
            elif coaching_signals.get("low_adherence"):
                action_percent = coaching_signals.get("action_percent")
                client["client_status_note"] = (
                    f"Action consistency {round(action_percent)}%"
                    if action_percent is not None
                    else "Low action consistency"
                )

        elif client["health_key"] == "review":
            week_number = ops.get("week_number") or client.get("current_week")
            client["client_status_note"] = (
                f"Week {week_number} ready to review"
                if week_number
                else "Coaching week ready to review"
            )

        elif ops.get("no_next_call"):
            client["client_status_note"] = "Next call not booked"

        if client.get("health_key") == "attention":
            last_nudge = latest_nudges.get(client["id"])
            client["last_nudge"] = last_nudge
            client["nudge_recent"] = nudge_is_recent(last_nudge)
            client["suggested_nudge_reason"] = (
                "missed_tracking"
                if (ops.get("missed_daily_count") or 0) >= 2
                else "low_adherence"
            )

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
        if client.get("health_key") == "attention"
    ]

    review_ready = [
        client
        for client in active_clients
        if client.get("health_key") == "review"
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
            "review_ready": review_ready,
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

    clean_name = name.strip()
    clean_email = email.strip() or None

    clean_phone = phone.strip()
    if clean_phone and not clean_phone.startswith("+"):
        clean_phone = f"{country_code.strip()} {clean_phone}".strip()
    clean_phone = clean_phone or None

    def normalized_phone(value: str | None) -> str:
        return "".join(
            character
            for character in (value or "")
            if character.isdigit()
        )

    normalized_new_email = (clean_email or "").lower()
    normalized_new_phone = normalized_phone(clean_phone)

    # Duplicate protection:
    # - email comparison is case-insensitive
    # - phone comparison ignores spaces, +, brackets and hyphens
    # - name is deliberately NOT used because two clients can share a name
    existing_clients = ClientService.dashboard_clients()

    for existing in existing_clients:
        existing_email = (
            existing.get("email") or ""
        ).strip().lower()
        existing_phone = normalized_phone(
            existing.get("phone")
        )

        duplicate_reason = None

        if (
            normalized_new_email
            and existing_email
            and normalized_new_email == existing_email
        ):
            duplicate_reason = "email"

        elif (
            normalized_new_phone
            and existing_phone
            and normalized_new_phone == existing_phone
        ):
            duplicate_reason = "phone"

        if duplicate_reason:
            # Do not create another row. Open the existing client workspace.
            return RedirectResponse(
                (
                    f"/dashboard/clients/{existing['id']}"
                    f"?duplicate={duplicate_reason}"
                ),
                status_code=303,
            )

    client_id = ClientService.create(
        name=clean_name,
        email=clean_email,
        phone=clean_phone,
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

    # SETUP STATE:
    # A brand-new client has no intake/start date yet. The template already
    # has a dedicated setup screen (`{% if not intake %}`), so return it now
    # instead of running the normal coaching-workspace services. Several of
    # those services assume an established coaching week and are irrelevant
    # until intake/setup has been completed.
    if not profile.get("intake"):
        return templates.TemplateResponse(
            "coach/client_workspace.html",
            {
                "request": request,
                "active_nav": "clients",
                "action_library": ACTION_LIBRARY,
                "call_time_slots": CALL_TIME_SLOTS,
                **profile,
            },
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
    current_week_actions = []
    next_week_actions = []
    coach_week_checkin = None
    client_weekly_reflection = None
    program_last_week_number = _program_length_weeks(profile["client"])
    has_next_program_week = True

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

        # Pull the exact same weekly reflection row that the client portal
        # saves/reads for this coaching week.
        client_weekly_reflection = get_weekly_reflection(
            client_id,
            coach_week_start,
        )

        # Find the saved coaching conversation for the selected week.
        # If older duplicate rows exist, checkins are newest-first, so the
        # newest record for that week is the editable source of truth.
        for saved_checkin in (profile.get("checkins") or []):
            saved_date = saved_checkin.get("call_date")
            if saved_date and coach_week_start <= saved_date <= coach_week_end:
                coach_week_checkin = saved_checkin
                break

        # Editable Weekly Coaching defaults come from the exact ACTIVE week
        # plan. The Data/history review may intentionally retain removed rows
        # that had past logs, and must not repopulate those rows in this form.
        #
        # If there is no explicit plan for this week at all, fall back to the
        # recovered/carry-forward week review (needed for historical gaps such
        # as Suganthi's original Week 2).
        exact_current_actions = _active_exact_week_actions(
            client_id,
            coach_week_start,
            coach_week_end,
        )
        if exact_current_actions:
            current_week_actions = exact_current_actions
        else:
            current_week_actions = [
                dict(action)
                for action in (week_review.get("actions") or [])
            ]

        # The next-week planning section disappears on the final program week.
        has_next_program_week = (
            program_last_week_number is None
            or coach_week_number < program_last_week_number
        )
        if has_next_program_week:
            next_week_number = coach_week_number + 1
            next_week_start = coach_week_end + timedelta(days=1)
            next_week_end = next_week_start + timedelta(days=6)
            next_week_actions = _active_exact_week_actions(
                client_id,
                next_week_start,
                next_week_end,
            )

    client_questions = get_client_questions(
        client_id,
        limit=50,
    )
    open_client_questions = [
        question
        for question in client_questions
        if question.get("status") == "open"
    ]
    if call_prep is not None:
        call_prep["client_questions"] = open_client_questions

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

    # The coach Data tab renders one transposed table per coaching week.
    # Build the week groups expected by templates/coach/client_workspace.html.
    history_weeks = []
    if coach_history_grid:
        grouped_history_weeks = {}
        current_history_week = coach_history_grid.get("current_week_number") or 0

        for row in coach_history_grid.get("rows") or []:
            week_number_for_row = row.get("week_number")
            if week_number_for_row is None:
                continue

            week = grouped_history_weeks.setdefault(
                week_number_for_row,
                {
                    "week_number": week_number_for_row,
                    "rows": [],
                    "measurement": None,
                    "is_current_week": week_number_for_row == current_history_week,
                },
            )
            week["rows"].append(row)

            if row.get("measurement"):
                week["measurement"] = row["measurement"]

        history_weeks = [
            grouped_history_weeks[week_number_key]
            for week_number_key in sorted(grouped_history_weeks, reverse=True)
        ]

    # Weekly Coaching must reload from the selected week's actual action plan.
    #
    # Do NOT overwrite current_week_actions from the normalized Data-grid
    # columns here.  Those grid columns are presentation/history structures and
    # can retain an older target value for the same stable action key.  Using
    # them as form defaults caused a saved target (for example 2 days) to reopen
    # as an older value (for example 4 days).
    #
    # current_week_actions was already loaded above from get_coach_week_review
    # for the exact selected coaching week, including historical carry-forward
    # recovery when that week has no explicit plan.  That is the authoritative
    # source for checkbox selection AND target/unit values.

    # Coaching intelligence for the current client workspace.
    # These are computed before TemplateResponse so the Jinja context never
    # references undefined variables.
    coaching_week_summary = (
        get_client_weekly_summary(
            client_id,
            week_start=week_start,
        )
        if week_start is not None
        else {}
    )
    progress_charts = get_client_progress_charts(
        client_id,
        weeks=12,
    )

    # Prepare independent builders for the selected week and following week.
    current_action_defaults, current_custom_actions = _week_action_defaults(
        current_week_actions
    )

    if has_next_program_week:
        plan_source_rows = next_week_actions or current_week_actions or []
        next_action_defaults, next_custom_actions = _week_action_defaults(
            plan_source_rows
        )
    else:
        next_action_defaults, next_custom_actions = {}, []

    # Keep enough custom rows for all carried-forward custom actions plus
    # a few blank rows for additions during the coaching call.
    current_custom_action_slot_count = max(
        5,
        len(current_custom_actions) + 3,
    )
    next_custom_action_slot_count = max(
        5,
        len(next_custom_actions) + 3,
    )

    client_resources = get_client_resources(client_id)
    available_resources = list_resources()
    client_workouts = get_client_workouts(client_id)
    available_workouts = list_workouts()
    client_timeline = build_client_timeline(profile["client"])
    coach_summary = build_coach_summary(call_prep, progress_summary)

    coaching_call_notes = get_call_notes(client_id, limit=20)
    latest_call_note = coaching_call_notes[0] if coaching_call_notes else None
    workflow_timeline = get_workflow_timeline(client_id, limit=30)

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
            "client_weekly_reflection": client_weekly_reflection,
            "client_questions": client_questions,
            "open_client_questions": open_client_questions,
            "coach_week_number": coach_week_number,
            "coach_week_start": coach_week_start,
            "coach_week_end": coach_week_end,
            "coach_week_is_current": coach_week_is_current,
            "coach_week_is_past": coach_week_is_past,
            "coach_week_is_future": coach_week_is_future,
            "coach_week_checkin": coach_week_checkin,
            "coach_week_can_previous": coach_week_number > 1,
            "coach_week_can_next": coach_week_number < min(week_number + 1, program_last_week_number or (week_number + 1)),
            "progress_summary": progress_summary,
            "coach_summary": coach_summary,
            "coach_history_grid": coach_history_grid,
            "history_weeks": history_weeks,
            "coaching_week_summary": coaching_week_summary,
            "progress_charts": progress_charts,
            "macro_settings": macro_settings,
            "macro_history": macro_history,
            "client_timeline": client_timeline,
            "coaching_call_notes": coaching_call_notes,
            "latest_call_note": latest_call_note,
            "workflow_timeline": workflow_timeline,
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
            "current_week_actions": current_week_actions,
            "current_action_defaults": current_action_defaults,
            "current_custom_actions": current_custom_actions,
            "current_custom_action_slot_count": current_custom_action_slot_count,
            "next_week_actions": next_week_actions,
            "next_action_defaults": next_action_defaults,
            "next_custom_actions": next_custom_actions,
            "next_custom_action_slot_count": next_custom_action_slot_count,
            "program_last_week_number": program_last_week_number,
            "has_next_program_week": has_next_program_week,
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



@router.post("/dashboard/clients/{client_id}/weekly/current")
def save_current_week_coaching(
    request: Request,
    client_id: int,
    selected_week_number: int = Form(...),
    call_date: str = Form(...),
    checkin_id: str = Form(""),
    wins: str = Form(""),
    struggles: str = Form(""),
    improvements_needed: str = Form(""),
    coach_support: str = Form(""),
    weekly_client_feedback: str = Form(""),
    weekly_private_note: str = Form(""),
    current_action_keys: list[str] = Form(default=[]),
    current_action_all_keys: list[str] = Form(default=[]),
    current_action_target_counts: list[str] = Form(default=[]),
    current_action_target_units: list[str] = Form(default=[]),
    current_custom_action_names: list[str] = Form(default=[]),
    current_custom_action_keys: list[str] = Form(default=[]),
    current_custom_target_counts: list[str] = Form(default=[]),
    current_custom_target_units: list[str] = Form(default=[]),
):
    if not coach_is_logged_in(request):
        return RedirectResponse("/coach/login", status_code=303)

    client = ClientService.get(client_id) or {}
    start_date = client.get("start_date")
    if not start_date:
        raise HTTPException(status_code=400, detail="Client start date is required")

    week_start = start_date + timedelta(days=(selected_week_number - 1) * 7)
    week_end = week_start + timedelta(days=6)

    parsed_call_date = date.fromisoformat(call_date)
    if not (week_start <= parsed_call_date <= week_end):
        raise HTTPException(
            status_code=400,
            detail=f"Coaching date must fall inside Week {selected_week_number}",
        )

    saved_checkin_id = ClientService.save_checkin(
        checkin_id=checkin_id.strip() or None,
        client_id=client_id,
        call_date=call_date,
        weight_kg=None,
        next_call_date=None,
        next_call_time=None,
        wins=wins.strip() or None,
        struggles=struggles.strip() or None,
        improvements_needed=improvements_needed.strip() or None,
        coach_support=coach_support.strip() or None,
        client_feedback=weekly_client_feedback.strip() or None,
        private_coach_note=weekly_private_note.strip() or None,
    )

    assignments = _submitted_assignments(
        selected_keys=current_action_keys,
        all_keys=current_action_all_keys,
        target_counts=current_action_target_counts,
        target_units=current_action_target_units,
        custom_names=current_custom_action_names,
        custom_keys=current_custom_action_keys,
        custom_counts=current_custom_target_counts,
        custom_units=current_custom_target_units,
    )
    _replace_week_actions(
        client_id=client_id,
        week_start=week_start,
        week_end=week_end,
        assignments=assignments,
        checkin_id=saved_checkin_id,
    )

    return RedirectResponse(
        f"/dashboard/clients/{client_id}?tab=weekly&week={selected_week_number}&current_saved=1",
        status_code=303,
    )


@router.post("/dashboard/clients/{client_id}/weekly/next")
def save_next_week_commitments(
    request: Request,
    client_id: int,
    source_week_number: int = Form(...),
    plan_week_number: int = Form(...),
    next_action_keys: list[str] = Form(default=[]),
    next_action_all_keys: list[str] = Form(default=[]),
    next_action_target_counts: list[str] = Form(default=[]),
    next_action_target_units: list[str] = Form(default=[]),
    next_custom_action_names: list[str] = Form(default=[]),
    next_custom_action_keys: list[str] = Form(default=[]),
    next_custom_target_counts: list[str] = Form(default=[]),
    next_custom_target_units: list[str] = Form(default=[]),
    workout_ids: list[int] = Form(default=[]),
):
    if not coach_is_logged_in(request):
        return RedirectResponse("/coach/login", status_code=303)

    client = ClientService.get(client_id) or {}
    start_date = client.get("start_date")
    if not start_date:
        raise HTTPException(status_code=400, detail="Client start date is required")

    if plan_week_number != source_week_number + 1:
        raise HTTPException(status_code=400, detail="Invalid next-week plan")

    program_last_week = _program_length_weeks(client)
    if program_last_week is not None and plan_week_number > program_last_week:
        raise HTTPException(status_code=400, detail="This is the final program week")

    plan_start = start_date + timedelta(days=(plan_week_number - 1) * 7)
    plan_end = plan_start + timedelta(days=6)

    assignments = _submitted_assignments(
        selected_keys=next_action_keys,
        all_keys=next_action_all_keys,
        target_counts=next_action_target_counts,
        target_units=next_action_target_units,
        custom_names=next_custom_action_names,
        custom_keys=next_custom_action_keys,
        custom_counts=next_custom_target_counts,
        custom_units=next_custom_target_units,
    )
    _replace_week_actions(
        client_id=client_id,
        week_start=plan_start,
        week_end=plan_end,
        assignments=assignments,
        checkin_id=None,
    )

    # Preserve the existing workout-library behaviour: selected workouts are
    # assigned to the client. (Workout assignments are not week-dated today.)
    for workout_id in workout_ids:
        assign_workout(
            workout_id=workout_id,
            client_ids=[client_id],
            coach_note=f"Week {plan_week_number} coaching plan",
        )

    return RedirectResponse(
        f"/dashboard/clients/{client_id}?tab=weekly&week={source_week_number}&next_saved=1",
        status_code=303,
    )


@router.post(
    "/dashboard/clients/{client_id}/checkin"
)
def add_client_checkin(
    request: Request,
    client_id: int,
    call_date: str = Form(...),
    checkin_id: str = Form(""),
    wins: str = Form(""),
    struggles: str = Form(""),
    improvements_needed: str = Form(""),
    coach_support: str = Form(""),
    weekly_client_feedback: str = Form(""),
    weekly_private_note: str = Form(""),
    action_keys: list[str] = Form(default=[]),
    action_all_keys: list[str] = Form(default=[]),
    action_target_counts: list[str] = Form(default=[]),
    action_target_units: list[str] = Form(default=[]),
    custom_action_names: list[str] = Form(default=[]),
    custom_action_keys: list[str] = Form(default=[]),
    custom_target_counts: list[str] = Form(default=[]),
    custom_target_units: list[str] = Form(default=[]),
):
    if not coach_is_logged_in(request):
        return RedirectResponse("/coach/login", status_code=303)

    checkin_id = ClientService.save_checkin(
        checkin_id=checkin_id.strip() or None,
        client_id=client_id,
        call_date=call_date,
        weight_kg=None,
        next_call_date=None,
        next_call_time=None,
        wins=wins.strip() or None,
        struggles=struggles.strip() or None,
        improvements_needed=improvements_needed.strip() or None,
        coach_support=coach_support.strip() or None,
        client_feedback=weekly_client_feedback.strip() or None,
        private_coach_note=weekly_private_note.strip() or None,
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

    existing_action_names = {
        row.get("action_name")
        for row in ClientService.actions(
            client_id,
            status="active",
            start_date=action_start_date,
            end_date=action_end_date,
        )
    }

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

    saved_client = ClientService.get(client_id) or {}
    saved_week_number, _, _ = _coaching_week_bounds(
        saved_client,
        date.fromisoformat(call_date),
    )
    week_query = f"&week={saved_week_number}" if saved_week_number else ""
    return RedirectResponse(
        f"/dashboard/clients/{client_id}?tab=weekly{week_query}",
        status_code=303,
    )
