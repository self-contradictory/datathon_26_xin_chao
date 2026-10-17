from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class Probe:
    key: str
    question: str
    kind: Literal["state", "action"]
    dwell: float


SCENE_CONTEXT = (
    "This is a ceiling security camera view of a bank cash desk. The cashier works behind "
    "the desk with a laptop, a cash counting machine and a safe; customers enter through "
    "the glass door and sit across the desk."
)

PROBES: tuple[Probe, ...] = (
    Probe('cashier_seated', 'Is the cashier sitting at the desk?', 'state', 12.0),
    Probe('customer_present', 'Is a customer at the desk, across from the cashier?', 'state', 12.0),
    Probe('person_in_doorway', 'Is someone walking through the doorway?', 'action', 3.0),
    Probe('counting_cash', 'Is the cashier counting banknotes?', 'action', 6.0),
    Probe('handover', 'Is an object visibly being transferred between the cashier and another person?', 'action', 3.0),
    Probe('using_computer', 'Is the cashier typing on the laptop?', 'action', 6.0),
    Probe('at_safe', 'Is someone standing at the safe?', 'action', 4.0),
    Probe('eating', 'Is the cashier eating or drinking?', 'action', 6.0),
    Probe('phone', 'Is the cashier using a mobile phone?', 'action', 6.0),
    Probe('room_occupied', 'Is anyone in the room?', 'state', 20.0),
    Probe('safe_open', 'Is the safe door open?', 'state', 15.0),
    Probe('screen_on', 'Is the computer screen turned on?', 'state', 30.0),
    Probe('cash_on_desk', 'Are banknotes lying on the desk?', 'state', 15.0),
    Probe('bag_on_desk', 'Is there a bag or package on the desk?', 'state', 20.0),
    Probe('food_on_desk', 'Is there food or a drink on the desk?', 'state', 20.0),
    Probe('door_open', 'Is the door open?', 'state', 10.0),
    Probe('stamps_on_desk', 'Are stamps or seals lying on the desk?', 'state', 20.0),
    Probe('key_in_safe', "Is a key sticking out of the safe's lock?", 'state', 20.0),
    Probe('id_document', 'Is someone holding an ID card or passport?', 'action', 3.0),
    Probe('cash_from_customer', 'Is the customer handing banknotes to the cashier?', 'action', 3.0),
    Probe('cash_to_customer', 'Is the cashier handing banknotes to the customer?', 'action', 3.0),
    Probe('personal_items', 'Is a handbag, purse or wallet lying on the desk?', 'state', 20.0),
    Probe('cashier_at_station', 'Is the cashier at the workstation, seated or standing?', 'state', 6.0),
)
