from enum import Enum
from typing import Union


class Deck(Enum):
    """List of the decks of cards available"""
    FIBONACCI = [0, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89]
    MODIFIED_FIBONACCI = [0, 0.5, 1, 2, 3, 5, 8, 13, 20, 40, 100]
    POWERS = [0, 1, 2, 4, 8, 16, 32, 64]
    TRUST_VOTE = [0, 1, 2, 3, 4, 5]
    T_SHIRTS = [1, 2, 3, 4, 5, 6, 7]  # Each value maps to a t-shirt size from XXS to XXL


# Decks whose cards are not shown as numbers. Must match the decks of the front-end (angular/src/app/model/deck.ts)
CARD_LABELS = {
    Deck.T_SHIRTS: {1: 'XXS', 2: 'XS', 3: 'S', 4: 'M', 5: 'L', 6: 'XL', 7: 'XXL'},
}


def has_points(deck: Deck) -> bool:
    """Whether the cards are points that can be added up (t-shirt sizes are not)"""
    return deck not in CARD_LABELS


def card_label(deck: Deck, card: Union[int, float, None]) -> str:
    """How a card is shown to the players: '5', '0.5' or 'XL'"""
    if card is None:
        return ''
    labels = CARD_LABELS.get(deck)
    if labels and card in labels:
        return labels[card]
    return str(int(card)) if float(card).is_integer() else str(card)


def card_from_label(deck: Deck, value: Union[str, int, float]) -> Union[int, float, None]:
    """The card matching a number or a label ('XL', '5', 0.5), or None if the deck has no such card"""
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.strip()
        for card, label in CARD_LABELS.get(deck, {}).items():
            if label.lower() == text.lower():
                return card
        try:
            value = float(text)
        except ValueError:
            return None
    if not isinstance(value, (int, float)):
        return None
    for card in deck.value:
        if card == value:
            return card
    return None
