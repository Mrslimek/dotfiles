import logging
from vkbottle.bot import BotLabeler, Message

from app.actions import GetCompanyInfoAction

logger = logging.getLogger(__name__)

labeler = BotLabeler()


@labeler.message(text="<query>")
async def get_company_handler(message: Message, query: str) -> None:
    try:
        validated = CompanyQuery(query=query)
    except ValueError as e:
        await message.answer(
            f"Неверный формат идентификатора: {e}"
        )
        return

    await message.answer("⏳ Ищу информацию...")

    try:
        action = GetCompanyInfoAction(validated.query)
        response_text = await action.execute()
    except Exception as e:
        logger.error(f"Error processing identifier {validated.query}: {e}")
        response_text = "Произошла ошибка при поиске информации. Попробуйте позже."

    await message.answer(response_text)
