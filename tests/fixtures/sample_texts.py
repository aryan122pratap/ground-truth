"""Sample texts used by the Streamlit 'Try an example' buttons and available
for tests. Chosen so a visitor with nothing to paste can still see the product
work in one click: one mostly-true, one mixed, one mostly-false."""

MOSTLY_TRUE = (
    "The Eiffel Tower was completed in 1889 for the World's Fair in Paris. "
    "It was designed by the engineer Gustave Eiffel's company. "
    "At 330 meters tall, it was the tallest man-made structure in the world "
    "until the Chrysler Building was completed in New York in 1930."
)

MIXED = (
    "SpaceX was founded by Elon Musk in 2002. "
    "The company's Falcon 9 rocket was the first orbital-class rocket capable of "
    "reflight, achieving this milestone in 2017. "
    "SpaceX has never had a launch failure in its entire history. "
    "I think SpaceX is the most important company operating today."
)

MOSTLY_FALSE = (
    "The Great Wall of China is visible from the Moon with the naked eye. "
    "Napoleon Bonaparte was famously very short, standing only about 5 feet tall. "
    "Humans only use 10 percent of their brains. "
    "Goldfish have a memory span of just three seconds."
)

EXAMPLES = [
    ("Mostly true", MOSTLY_TRUE),
    ("Mixed", MIXED),
    ("Mostly false", MOSTLY_FALSE),
]
