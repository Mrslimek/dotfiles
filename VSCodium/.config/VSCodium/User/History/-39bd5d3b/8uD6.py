import asyncio
import logging
import sys

from app import bot


def setup_logging() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )
    return logging.getLogger(__name__)


def main() -> int:
    logger = setup_logging()

    from app.config import config
    logger.info("Configuration:")
    logger.info(f"  API Base URL: {config.api_base_url}")
    logger.info(f"  Log Level: {config.LOG_LEVEL}")
    logger.info("")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        bot.run_forever()
        return 0

    except KeyboardInterrupt:
        logger.info("")
        logger.info("=" * 60)
        logger.info("  Bot stopped by user (Ctrl+C)")
        logger.info("=" * 60)
        return 0

    except Exception as e:
        logger.error("")
        logger.error("=" * 60)
        logger.error("  Fatal error occurred!")
        logger.error("=" * 60)
        logger.error(f"Error: {e}", exc_info=True)
        logger.error("")

        if "Access denied" in str(e) or "no access" in str(e):
            logger.error("VK API Permission Error!")
            logger.error("  Your VK token lacks necessary permissions.")
            logger.error("")
            logger.error("To fix:")
            logger.error("  1. Go to: https://vk.com/group<GROUP_ID>?act=manage")
            logger.error("  2. Navigate to: Управление → Работа с API")
            logger.error("  3. Create access token with 'Сообщения' permission")
            logger.error("  4. Update VK_TOKEN in your .env file")

        elif "token" in str(e).lower() and "valid" in str(e).lower():
            logger.error("Invalid VK Token!")
            logger.error("  Your VK token may be expired or incorrect.")
            logger.error("  Please regenerate it from VK group settings.")

        elif "Unauthorized" in str(e) or "401" in str(e):
            logger.error("API Unauthorized!")
            logger.error("  Check your credentials in .env")
            logger.error("  Ensure the token is valid and not expired")

        logger.error("")
        logger.error("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
