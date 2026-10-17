from backend.reconstruction.probes import SCENE_CONTEXT

STATES = {
    "cashier_seated": "the cashier sits at the desk",
    "cashier_at_station": "the cashier is at the workstation, seated or standing",
    "customer_present": "a customer is at the desk, across from the cashier",
    "room_occupied": "anyone is in the room",
    "safe_open": "the safe door is open",
    "key_in_safe": "a key sticks out of the safe's lock",
    "screen_on": "the laptop screen is on",
    "cash_on_desk": "banknotes lie on the desk",
    "bag_on_desk": "a bag or package lies on the desk",
    "food_on_desk": "food or a drink is on the desk",
    "stamps_on_desk": "stamps or seals lie on the desk",
    "personal_items": "a handbag, purse or wallet lies on the desk",
    "door_open": "the door is open",
}

ACTIONS = {
    "person_in_doorway": "someone walks through the doorway",
    "counting_cash": "the cashier counts banknotes by hand or with the counting machine",
    "cash_from_customer": "the customer hands banknotes to the cashier",
    "cash_to_customer": "the cashier hands banknotes to the customer",
    "handover": "an object passes between the cashier and another person",
    "using_computer": "the cashier types on the laptop",
    "at_safe": "someone stands at the safe",
    "eating": "the cashier eats or drinks",
    "phone": "the cashier uses a mobile phone",
    "id_document": "someone holds an ID card or passport",
}


def _listing(terms: dict[str, str]) -> str:
    return "\n".join(f"- {name}: {meaning}" for name, meaning in terms.items())


def _clip(start: float, end: float) -> str:
    return (f"The video covers {start:.1f}-{end:.1f} s of the recording. Its timestamps are seconds "
            "from the start of the recording.")


ACTION_INSTRUCTIONS = (
    f"Actions:\n{_listing(ACTIONS)}\n"
    "List every action with its start_sec, end_sec, actor and recipient, in seconds from the start "
    "of the recording. Use a listed name when it fits; otherwise name the action with a short "
    "snake_case phrase, such as customer_signs_document."
)


def _graph_instructions(source: str) -> str:
    return (
        f"States:\n{_listing(STATES)}\n"
        f"Put a state in true_states with each stretch of time {source} shows it holding; it is false for "
        f"the rest of the clip. Put a state in false_states when {source} shows it false for the whole "
        f"clip. Leave out a state {source} does not settle.\n" + ACTION_INSTRUCTIONS
    )


def structured_prompt(start: float, end: float, dense: bool = False) -> str:
    states = (
        f"States:\n{_listing(STATES)}\n"
        "Give every listed state one entry per stretch of time, with value true, false or unknown "
        "(unknown when the video does not show it), start_sec and end_sec.\n" + ACTION_INSTRUCTIONS
    ) if dense else _graph_instructions("the video")
    return (
        f"{SCENE_CONTEXT}\n{_clip(start, end)}\n"
        "Write the clip as a timeline graph. Report only what is visible, briefly and literally.\n" + states
    )


def caption_prompt(start: float, end: float) -> str:
    return (
        f"{SCENE_CONTEXT}\n{_clip(start, end)}\n"
        "Describe what happens, briefly and literally, as timestamped lines such as "
        "\"4.5-6.0 s: the cashier counts banknotes by hand.\"\n"
        "Cover what you can see of:\n"
        "- the cashier and any customer: where each is, whether seated, and what their hands do "
        "(money, documents, ID cards, laptop, phone, food or drink);\n"
        "- anyone walking through the doorway, and whether the door is open;\n"
        "- the safe: open or closed, and whether a key is in its lock;\n"
        "- the desk: banknotes, bags or packages, stamps or seals, food or drinks, handbags, purses or wallets;\n"
        "- whether the laptop screen is on.\n"
        "Say when something cannot be seen. Do not judge whether a rule was broken."
    )


def analyzer_prompt(start: float, end: float, caption: str) -> str:
    return (
        f"Below is a description of the {start:.1f}-{end:.1f} s clip of a recording from a ceiling camera "
        "over a bank cash desk. Convert it into a timeline graph. Use only what the description states; "
        "do not add actions, objects or states.\n"
        + _graph_instructions("the description")
        + f"\nDescription:\n{caption}"
    )
