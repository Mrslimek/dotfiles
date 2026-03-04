import logging
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field
from app.actions import GetCompanyInfoAction
from vkbottle.bot import BotLabeler, Message

logger = logging.getLogger(__name__)

labeler = BotLabeler()


@labeler.message(text="<query>")
async def get_company_handler(message: Message, query: str) -> None:
    try:
        query = CompanyQuery(query=query).model_dump()
    except ValueError as e:
        await message.answer(
            f"Неверный формат идентификатора: {e}"
        )
        return

    await message.answer("⏳ Ищу информацию...")

    try:
        response_text = await GetCompanyInfoAction(query).execute()

    except Exception as e:
        logger.error(f"Error processing identifier {validated.query}: {e}")
        response_text = "Произошла ошибка при поиске информации. Попробуйте позже."

    await message.answer(response_text)


def validate_ru_inn_or_ogrn(value: str) -> str:
    """
    Validates Russian taxpayer (INN) and registration (OGRN/OGRNIP) numbers.
    
    References (Russian Standards):
    - ИНН: Приказ ФНС России от 29.06.2012 N ММВ-7-6/435@
    - ОГРН: Постановление Правительства РФ от 17.05.2002 N 438
    - ОГРНИП: Приказ ФНС России от 25.01.2012 N ММВ-7-6/25@
    """
    v = value.strip()

    if not v.isdigit():
        raise ValueError("Identifier must contain only digits")

    length = len(v)

    def check_inn_10(s: str) -> bool:
        w = [2, 4, 10, 3, 5, 9, 4, 6, 8]
        checksum = sum(int(s[i]) * w[i] for i in range(9))
        return (checksum % 11) % 10 == int(s[9])

    def check_inn_12(s: str) -> bool:
        w1 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        w2 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        c1 = (sum(int(s[i]) * w1[i] for i in range(10)) % 11) % 10
        c2 = (sum(int(s[i]) * w2[i] for i in range(11)) % 11) % 10
        return c1 == int(s[10]) and c2 == int(s[11])

    if length == 10:
        if not check_inn_10(v):
            raise ValueError("Invalid checksum for INN (10 digits)")
    elif length == 12:
        if not check_inn_12(v):
            raise ValueError("Invalid checksum for INN (12 digits)")
    elif length == 13:
        if (int(v[:-1]) % 11) % 10 != int(v[-1]):
            raise ValueError("Invalid checksum for OGRN (13 digits)")
    elif length == 15:
        if (int(v[:-1]) % 13) % 10 != int(v[-1]):
            raise ValueError("Invalid checksum for OGRNIP (15 digits)")
    else:
        raise ValueError("Invalid length. Supported: 10, 12 (INN) or 13, 15 (OGRN)")

    return v


CompanyIdentifier = Annotated[
    str,
    AfterValidator(validate_ru_inn_or_ogrn),
    Field(description="Russian INN, OGRN or OGRNIP identifier")
]


class CompanyQuery(BaseModel):
    query: CompanyIdentifier


@labeler.message()
async def handle_unknown_message(message: Message) -> None:
    help_text = (
        "Привет! Я бот для поиска информации по ИНН.\n\n"
        "Просто отправьте мне ИНН (10 или 12 цифр), "
        "и я найду информацию о компании или ИП.\n\n"
        "Пример: 7728168971"
    )

    await message.answer(help_text)
