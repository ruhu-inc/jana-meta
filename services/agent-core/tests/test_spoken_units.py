"""VOC-08: a quantity's unit is spoken as words ("metres per second squared", never "m over s squared"), for every
unit the Maths and Physics packs use, written plain, with Unicode symbols or in TeX. The screen keeps the symbols:
only the speech text changes. Readings are authored independently of the parser's tables."""

import pytest
from agent_core.engine.verbaliser import FALLBACK, verbalise

# Every unit the Maths and Physics packs give an answer in (content/curriculum/{mth,phy}, `unit:`), after a number.
PACK_UNITS = [
    ("m", "metres"),
    ("cm", "centimetres"),
    ("mm", "millimetres"),
    ("km", "kilometres"),
    ("nm", "nanometres"),
    ("s", "seconds"),
    ("ms", "milliseconds"),
    ("min", "minutes"),
    ("h", "hours"),
    ("kg", "kilograms"),
    ("g", "grams"),
    ("N", "newtons"),
    ("kN", "kilonewtons"),
    ("J", "joules"),
    ("kJ", "kilojoules"),
    ("MJ", "megajoules"),
    ("W", "watts"),
    ("kW", "kilowatts"),
    ("MW", "megawatts"),
    ("kWh", "kilowatt hours"),
    ("Pa", "pascals"),
    ("kPa", "kilopascals"),
    ("mmHg", "millimetres of mercury"),
    ("Hz", "hertz"),
    ("kHz", "kilohertz"),
    ("V", "volts"),
    ("mV", "millivolts"),
    ("kV", "kilovolts"),
    ("A", "amperes"),
    ("mA", "milliamperes"),
    ("C", "coulombs"),
    ("nC", "nanocoulombs"),
    ("Ω", "ohms"),
    ("kΩ", "kilohms"),
    ("K", "kelvin"),
    ("°C", "degrees Celsius"),
    ("Bq", "becquerels"),
    ("kBq", "kilobecquerels"),
    ("MBq", "megabecquerels"),
    ("m/s", "metres per second"),
    ("m/s^2", "metres per second squared"),
    ("km/s", "kilometres per second"),
    ("km/h", "kilometres per hour"),
    ("m^2", "metres squared"),
    ("cm^2", "centimetres squared"),
    ("cm^3", "centimetres cubed"),
    ("g/cm^3", "grams per centimetre cubed"),
    ("kg/m^3", "kilograms per metre cubed"),
    ("N/kg", "newtons per kilogram"),
    ("N/m", "newtons per metre"),
    ("N m", "newton metres"),
    ("kg m/s", "kilogram metres per second"),
    ("kJ/kg", "kilojoules per kilogram"),
    ("°C/min", "degrees Celsius per minute"),
    ("counts/min", "counts per minute"),
]


@pytest.mark.parametrize(("unit", "words"), PACK_UNITS)
def test_every_pack_unit_is_spoken_as_words(unit, words):
    assert verbalise(f"It is 12 {unit}.").text == f"It is twelve {words}."


WRITTEN = [
    # The reading the task names: never "m over s squared".
    ("a = 9.8 m/s^2", "a equals nine point eight metres per second squared"),
    ("a = 9.8 m/s²", "a equals nine point eight metres per second squared"),
    ("a = 9.8 m s^-2", "a equals nine point eight metres per second squared"),
    ("a = 9.8 m s⁻²", "a equals nine point eight metres per second squared"),
    (r"$a = 9.8\,\text{m/s}^2$", "a equals nine point eight metres per second squared"),
    (r"$a = 9.8\ \mathrm{m\,s^{-2}}$", "a equals nine point eight metres per second squared"),
    (r"$9.8\,\text{m s}^{-2}$", "nine point eight metres per second squared"),
    ("F = 12 N", "F equals twelve newtons"),
    ("R = 4 Ω", "R equals four ohms"),
    (r"$R = 4\,\Omega$", "R equals four ohms"),
    ("T = 25 °C", "T equals twenty five degrees Celsius"),
    ("The angle is 30°.", "The angle is thirty degrees."),
    ("The area is 5 cm².", "The area is five centimetres squared."),
    ("The volume is 20 cm³.", "The volume is twenty centimetres cubed."),
    ("c = 4200 J/(kg °C)", "c equals four thousand two hundred joules per kilogram per degree Celsius"),
    ("It weighs 1 N.", "It weighs one newton."),
    ("It moves at 1 m/s.", "It moves at one metre per second."),
    ("It takes 1 h.", "It takes one hour."),
    ("1.5 m", "one point five metres"),
    ("A 5cm line", "A five centimetres line"),
    ("It is 20kg.", "It is twenty kilograms."),
    (r"$1.6 \times 10^{-19}\,\text{C}$", "one point six times ten to the power negative nineteen, end power coulombs"),
    ("v = 20 m/s and t = 4 s", "v equals twenty metres per second and t equals four seconds"),
    # A bare unit group in TeX reads in words, as before.
    (r"\text{kg}", "kilograms"),
    (r"\text{m/s}^2", "metres per second squared"),
]


@pytest.mark.parametrize(("written", "spoken"), WRITTEN)
def test_units_are_spoken_as_words(written, spoken):
    assert verbalise(written).text == spoken


UNCHANGED = [
    # Letters that are not units after a number stay what they were: variables, ordinals, words.
    (r"$v^2 = u^2 + 2as$", "v squared equals u squared plus two a s"),
    ("2ab", "two a b"),
    (r"$2m + 3$", "two m plus three"),
    ("Step 1: subtract.", "Step one: subtract."),
    ("It came 2nd.", "It came two nd."),
    ("We have 3 apples.", "We have three apples."),
    ("5/2", "five over two"),
    ("x = 6 / 2", "x equals six over two"),
    # A glued single letter is not a unit: 1990s is a decade, not seconds.
    ("In the 1990s.", "In the one thousand nine hundred ninety s."),
    # Powers the reading does not support are never half read.
    (r"\text{m s}^{-4}", FALLBACK),
    ("x²", FALLBACK),
]


@pytest.mark.parametrize(("written", "spoken"), UNCHANGED)
def test_other_letters_after_numbers_are_not_units(written, spoken):
    assert verbalise(written).text == spoken
