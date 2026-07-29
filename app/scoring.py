from datetime import datetime, timezone


FEELING_SCORES = {
    "not-self": 36,
    "out-control": 28,
    "frustrated": 45,
    "stuck": 40,
    "starting-over": 32,
}


def scale(value: str) -> int:
    scale_map = {
        1: 25,
        2: 50,
        3: 72,
        4: 92,
    }

    try:
        numeric_value = int(value)
    except (TypeError, ValueError):
        return 50

    return scale_map.get(numeric_value, 50)


def average(values: list[int]) -> int:
    return round(sum(values) / len(values))


def calculate_score(answers: dict[str, str]) -> dict:
    wake = scale(answers.get("wake", "2"))
    energy = scale(answers.get("energy", "2"))
    cravings = scale(answers.get("cravings", "2"))
    sleep = scale(answers.get("sleep", "2"))
    stress = scale(answers.get("stress", "2"))
    consistency = scale(answers.get("consistency", "2"))

    feeling = answers.get("feeling", "")
    confidence = FEELING_SCORES.get(feeling, 40)

    dimensions = {
        "recovery": average([wake, sleep, stress]),
        "metabolic": average([wake, energy]),
        "nutrition": cravings,
        "behaviour": consistency,
        "confidence": confidence,
    }

    total = round(
        dimensions["recovery"] * 0.28
        + dimensions["metabolic"] * 0.22
        + dimensions["nutrition"] * 0.18
        + dimensions["behaviour"] * 0.18
        + dimensions["confidence"] * 0.14
    )

    ordered_dimensions = sorted(
        dimensions.items(),
        key=lambda item: item[1]
    )

    return {
        "answers": answers,
        "dimensions": dimensions,
        "total": total,
        "opportunity": ordered_dimensions[0][0],
        "strength": ordered_dimensions[-1][0],
        "bodyProfile": answers.get("body"),
        "feeling": feeling,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
