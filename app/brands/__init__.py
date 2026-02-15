from app.brands.bestshield import BestShieldProcessor
from app.brands.shabah import ShabahProcessor
from app.brands.alarabi import AlArabiProcessor

BRAND_PROCESSORS = {
    "bestshield": BestShieldProcessor,
    "shabah": ShabahProcessor,
    "alarabi": AlArabiProcessor,
}


def get_processor(brand_key: str):
    processor_class = BRAND_PROCESSORS.get(brand_key)
    if not processor_class:
        raise ValueError(f"Unknown brand processor: {brand_key}")
    return processor_class()
