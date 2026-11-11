class PlanningPokerException(Exception):
    code = 0


class DeckDoesNotExistError(PlanningPokerException):
    code = 4001


class GameNotOngoingError(PlanningPokerException):
    code = 4002


class PlayerNotInGameError(PlanningPokerException):
    code = 4003


class GameDoesNotExistError(PlanningPokerException):
    code = 4004


class InvalidCardValueError(PlanningPokerException):
    code = 4005


class SpectatorCannotPlayError(PlanningPokerException):
    code = 4006


class StoryDoesNotExistError(PlanningPokerException):
    code = 4008


class InvalidStoryError(PlanningPokerException):
    code = 4009


class AgentAccessDeniedError(PlanningPokerException):
    code = 4010


class TooManyGamesCreatedError(PlanningPokerException):
    code = 4011

    def __init__(self, retry_after: int):
        super().__init__(f'Too many games created from this address: try again in {retry_after} seconds, or reuse an '
                         f'existing game (its links keep working)')
        self.retry_after = retry_after
