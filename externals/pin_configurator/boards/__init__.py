from .mspm0g3507_48qfp import build_mspm0g3507_48qfp
from .rpi_pico import build_rpi_pico

from .stm32l476_lqfp64 import build_stm32l476_lqfp64
from .stm32l476_wlcsp72 import build_stm32l476_wlcsp72
from .stm32l476_wlcsp81 import build_stm32l476_wlcsp81
from .stm32l476_lqfp100 import build_stm32l476_lqfp100
from .stm32l476_ufbga132 import build_stm32l476_ufbga132
from .stm32l476_lqfp144 import build_stm32l476_lqfp144
from .stm32l476_ufbga144 import build_stm32l476_ufbga144

from .stm32f411_ufqfpn48 import build_stm32f411_ufqfpn48
from .stm32f411_wlcsp49 import build_stm32f411_wlcsp49
from .stm32f411_lqfp100 import build_stm32f411_lqfp100
from .stm32f411_ufbga100 import build_stm32f411_ufbga100


from .stm32f427_ufbga2 import build_stm32f427_ufbga2
from .stm32f427_lqfp100 import build_stm32f427_lqfp100
from .stm32f427_wlcsp143 import build_stm32f427_wlcsp143
from .stm32f427_lqfp144 import build_stm32f427_lqfp144
from .stm32f427_ufbga169 import build_stm32f427_ufbga169
from .stm32f427_lqfp176 import build_stm32f427_lqfp176
from .stm32f427_lqfp208 import build_stm32f427_lqfp208
from .stm32f427_bga216 import build_stm32f427_bga216

from .stm32f411_lqfp64 import build_stm32f411_lqfp64

BOARDS = {
    "mspm0g3507": build_mspm0g3507_48qfp,
    "rpi_pico": build_rpi_pico,
    "stm32l476_lqfp64": build_stm32l476_lqfp64,
    "stm32l476_wlcsp72": build_stm32l476_wlcsp72,
    "stm32l476_wlcsp81": build_stm32l476_wlcsp81,
    "stm32l476_lqfp100": build_stm32l476_lqfp100,
    "stm32l476_ufbga132": build_stm32l476_ufbga132,
    "stm32l476_lqfp144": build_stm32l476_lqfp144,
    "stm32l476_ufbga144": build_stm32l476_ufbga144,
    "stm32f411_ufqfpn48": build_stm32f411_ufqfpn48,
    "stm32f411_wlcsp49": build_stm32f411_wlcsp49,
    "stm32f411_lqfp100": build_stm32f411_lqfp100,
    "stm32f411_ufbga100": build_stm32f411_ufbga100,
    "stm32f427_ufbga2": build_stm32f427_ufbga2,
    "stm32f427_lqfp100": build_stm32f427_lqfp100,
    "stm32f427_wlcsp143": build_stm32f427_wlcsp143,
    "stm32f427_lqfp144": build_stm32f427_lqfp144,
    "stm32f427_ufbga169": build_stm32f427_ufbga169,
    "stm32f427_lqfp176": build_stm32f427_lqfp176,
    "stm32f427_lqfp208": build_stm32f427_lqfp208,
    "stm32f427_bga216": build_stm32f427_bga216,
    "stm32f411_lqfp64": build_stm32f411_lqfp64,
}
