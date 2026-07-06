def format_recommended(route: dict) -> str:
    lines = []

    title = route.get("title", "")
    merchant = route.get("merchant", "")
    listed_price = route.get("listed_price", 0)
    final_cost = route.get("final_cost", 0)
    voucher = route.get("voucher")
    card_fomo = route.get("card_fomo")
    sellers = route.get("sellers", [])

    lines.append(f"*{title}* — Best way to buy ⭐")
    lines.append("")

    lines.append(f"🏪 *{merchant}*")

    if listed_price and final_cost and final_cost < listed_price:
        savings = listed_price - final_cost
        lines.append(f"💰 Final cost: ₹{final_cost:,.0f} _(was ₹{listed_price:,.0f})_")
        lines.append(f"✅ You save: ₹{savings:,.0f}")
    else:
        lines.append(f"💰 Final cost: ₹{final_cost:,.0f}")

    if sellers:
        seller = sellers[0]
        link = seller.get("link", "")
        if link:
            lines.append(f"🔗 {link}")

    if voucher:
        brand = voucher.get("brand", "")
        discount = voucher.get("best_discount", 0)
        denomination = voucher.get("recommended_denomination", 0)
        lines.append("")
        lines.append(f"🎟 *Gyftr Voucher — {brand}*")
        lines.append(f"Buy ₹{denomination:,.0f} voucher at {discount}% off before checkout")
        redeem_url = voucher.get("gyftr_url", "")
        if redeem_url:
            lines.append(f"Buy voucher: {redeem_url}")

    if card_fomo:
        card_name = card_fomo.get("card_name", "")
        extra_saving = card_fomo.get("actual_saving", 0)
        final_with_card = card_fomo.get("final_cost_with_card", 0)
        lines.append("")
        lines.append(f"💳 Have an *{card_name}* card?")
        lines.append(f"Pay with it at checkout to save an extra ₹{extra_saving:,.0f}")
        lines.append(f"Your final cost: ₹{final_with_card:,.0f}")

    return "\n".join(lines) + "\n"


def format_alternative(index: int, route: dict) -> str:
    lines = []

    title = route.get("title", "")
    merchant = route.get("merchant", "")
    listed_price = route.get("listed_price", 0)
    final_cost = route.get("final_cost", 0)
    voucher = route.get("voucher")
    sellers = route.get("sellers", [])

    lines.append(f"*Option {index} — {title}*")
    lines.append(f"🏪 {merchant}")

    if listed_price and final_cost and final_cost < listed_price:
        savings = listed_price - final_cost
        lines.append(f"💰 ₹{final_cost:,.0f} _(save ₹{savings:,.0f})_")
    else:
        lines.append(f"💰 ₹{final_cost:,.0f}")

    if sellers:
        seller = sellers[0]
        link = seller.get("link", "")
        delivery = seller.get("delivery", "")
        if delivery:
            lines.append(f"🚚 {delivery[:60]}")
        if link:
            lines.append(f"🔗 {link}")

    if voucher:
        brand = voucher.get("brand", "")
        discount = voucher.get("best_discount", 0)
        denomination = voucher.get("recommended_denomination", 0)
        lines.append(f"🎟 Use {brand} Gyftr voucher — buy ₹{denomination:,.0f} at {discount}% off")

    return "\n".join(lines) + "\n"
