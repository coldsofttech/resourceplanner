def get_tshirt_size(amount):
    from apps.configurations.services import ConfigurationService
    from decimal import Decimal

    if amount is None:
        return None

    amount = Decimal(str(amount))
    bands = [
        ("XS", ConfigurationService.get_float("BUDGET_SIZE_XS_MAX_AMOUNT", 20000)),
        ("S", ConfigurationService.get_float("BUDGET_SIZE_S_MAX_AMOUNT", 60000)),
        ("M", ConfigurationService.get_float("BUDGET_SIZE_M_MAX_AMOUNT", 200000)),
        ("L", ConfigurationService.get_float("BUDGET_SIZE_L_MAX_AMOUNT", 500000)),
    ]
    for label, max_amount in bands:
        if amount <= Decimal(str(max_amount)):
            return label
    return "XL"


def get_tshirt_size_definitions():
    from apps.configurations.services import ConfigurationService
    from decimal import Decimal

    xs_max = ConfigurationService.get_float("BUDGET_SIZE_XS_MAX_AMOUNT", 20000)
    s_max = ConfigurationService.get_float("BUDGET_SIZE_S_MAX_AMOUNT", 60000)
    m_max = ConfigurationService.get_float("BUDGET_SIZE_M_MAX_AMOUNT", 200000)
    l_max = ConfigurationService.get_float("BUDGET_SIZE_L_MAX_AMOUNT", 500000)

    def fmt(val):
        v = (
            int(val)
            if Decimal(str(val)) == Decimal(str(val)).to_integral_value()
            else val
        )
        return f"£{v:,}"

    return [
        {"size": "XS", "label": "X-Small", "description": f"≤ {fmt(xs_max)}"},
        {"size": "S", "label": "Small", "description": f"{fmt(xs_max)} – {fmt(s_max)}"},
        {"size": "M", "label": "Medium", "description": f"{fmt(s_max)} – {fmt(m_max)}"},
        {"size": "L", "label": "Large", "description": f"{fmt(m_max)} – {fmt(l_max)}"},
        {"size": "XL", "label": "X-Large", "description": f"> {fmt(l_max)}"},
    ]
