from datetime import datetime

import pytz
from pydantic.functional_validators import AfterValidator
from typing_extensions import Annotated


def localize(v: datetime) -> datetime:
    # localize the date to the Asia/Kolkata timezone
    tz = pytz.timezone('Asia/Kolkata')
    print(f'Localizing {v} to {tz} to be {v.astimezone(tz)}')
    return v.astimezone(tz)


LocalizedDateTime = Annotated[datetime, AfterValidator(localize)]
