"""Controlled vocabulary enums for DSL and runtime."""

from enum import Enum


class AssetClass(str, Enum):
    EQUITY = "equity"
    INDEX = "index"
    FUND = "fund"
    FUTURES = "futures"
    COMMODITY = "commodity"


class CallPut(str, Enum):
    CALL = "call"
    PUT = "put"


class ExerciseType(str, Enum):
    EUROPEAN = "european"
    AMERICAN = "american"
    ASIAN = "asian"
    BERMUDAN = "bermudan"


class BarrierType(str, Enum):
    UP_AND_OUT = "up_and_out"
    UP_AND_IN = "up_and_in"
    DOWN_AND_OUT = "down_and_out"
    DOWN_AND_IN = "down_and_in"


class UpDown(str, Enum):
    UP = "up"
    DOWN = "down"


class InOut(str, Enum):
    IN = "in"
    OUT = "out"


class PaymentType(str, Enum):
    HIT = "hit"
    EXPIRE = "expire"


class AverageMethod(str, Enum):
    GEOMETRIC = "geometric"
    ARITHMETIC = "arithmetic"


class AsianAveSubstitution(str, Enum):
    UNDERLYING = "underlying"
    STRIKE = "strike"


class EngineMethod(str, Enum):
    ANALYTIC = "analytic"
    TREE = "tree"
    FDM = "fdm"
    MC = "mc"
    QUAD = "quad"


class VolType(str, Enum):
    CONSTANT = "constant"
    LOCAL = "local"
    SURFACE = "surface"
    STOCHASTIC = "stochastic"
    JUMP = "jump"


class ProcessType(str, Enum):
    BSM = "bsm"
    HESTON = "heston"
    LEVY = "levy"
    LEVY_GARCH = "levy_garch"
    SCENARIO = "scenario"


class DayCount(str, Enum):
    ACT365 = "ACT/365"
    ACT360 = "ACT/360"
    ACT_ACT = "ACT/ACT"
    THIRTY360 = "30/360"


class Compounding(str, Enum):
    SIMPLE = "simple"
    CONTINUOUS = "continuous"
    ANNUAL = "annual"


class BusinessConvention(str, Enum):
    PRECEDING = "preceding"
    FOLLOWING = "following"
    MODIFIED_FOLLOWING = "modified_following"


class RandsMethod(str, Enum):
    PSEUDO = "pseudo"
    SOBOL = "sobol"
    HALTON = "halton"


class QuadMethod(str, Enum):
    FFT = "fft"
    SIMPSON = "simpson"
    TRAPEZOID = "trapezoid"


class AlignPolicy(str, Enum):
    SAME_DAY = "same_day"
    PREV_BUSINESS_DAY = "prev_business_day"
    NEAREST_AVAILABLE = "nearest_available"


class AdjFlag(str, Enum):
    NONE = "none"
    FORWARD = "forward"
    BACKWARD = "backward"


class FdmScheme(str, Enum):
    EXPLICIT = "explicit"
    IMPLICIT = "implicit"
    CRANK_NICOLSON = "crank_nicolson"
