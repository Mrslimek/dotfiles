from app.services.podruchniy_service import PodruchniyService


class GetCompanyInfoAction:
    def __init__(self, query: str) -> None:
        self.query: str = query
        self.service = PodruchniyService()

    async def execute(self, identifier: str) -> str:
        result = await P.find_by_id_party(identifier)
        return self._format_response(result)

    def _format_response(self, data: dict) -> str:
        if isinstance(data, list):
            if not data:
                return "Информация не найдена"
            data = data[0]

        company_data = data.get("data", {})
        if not company_data:
            return "Информация не найдена"

        name_info = company_data.get("name") or {}
        if not isinstance(name_info, dict):
            name_info = {}
        name = name_info.get("full_with_opf") or name_info.get("short_with_opf") or "Не указано"

        inn = company_data.get("inn") or "Не указано"
        kpp = company_data.get("kpp") or "Не указано"
        ogrn = company_data.get("ogrn") or "Не указано"

        address_info = company_data.get("address") or {}
        if not isinstance(address_info, dict):
            address_info = {}
        address = address_info.get("value") or address_info.get("unrestricted_value") or "Не указано"

        state_info = company_data.get("state") or {}
        if not isinstance(state_info, dict):
            state_info = {}
        status = state_info.get("status") or "Не указано"

        management_info = company_data.get("management") or {}
        if not isinstance(management_info, dict):
            management_info = {}
        manager_name = management_info.get("name") or ""
        manager_post = management_info.get("post") or ""

        opf_info = company_data.get("opf") or {}
        if not isinstance(opf_info, dict):
            opf_info = {}
        opf = opf_info.get("short") or ""

        status_map = {
            "ACTIVE": "Действующая",
            "LIQUIDATED": "Ликвидирована",
            "LIQUIDATING": "Ликвидируется",
            "REORGANIZING": "В процессе реорганизации",
            "BANKRUPT": "Банкрот",
            "CLOSED": "Закрыта",
            "ELIMINATED": "Исключена",
            "NON_EXISTENT": "Не существует",
            "REGISTERED": "Зарегистрирована",
            "REORGANIZED": "Реорганизована",
        }
        status_ru = status_map.get(status, status or "Не указано")

        response_parts = []
        response_parts.append("📋 Информация о компании:")
        response_parts.append("")

        if opf:
            response_parts.append(f"🏢 {opf}")
        response_parts.append(f"📛 {name}")
        response_parts.append("")
        response_parts.append("🆔 Реквизиты:")
        response_parts.append(f"   ИНН: {inn}")
        if kpp != "Не указано":
            response_parts.append(f"   КПП: {kpp}")
        if ogrn != "Не указано":
            response_parts.append(f"   ОГРН: {ogrn}")
        response_parts.append("")
        response_parts.append("📍 Адрес:")
        response_parts.append(f"   {address}")
        response_parts.append("")
        response_parts.append(f"✅ Статус: {status_ru}")

        if manager_name or manager_post:
            response_parts.append("")
            response_parts.append("👤 Руководитель:")
            if manager_post:
                response_parts.append(f"   {manager_post}")
            if manager_name:
                response_parts.append(f"   {manager_name}")

        return "\n".join(response_parts)
