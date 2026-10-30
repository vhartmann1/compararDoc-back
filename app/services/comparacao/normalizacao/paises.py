"""País pela sigla ISO de 2 letras."""

from app.services.comparacao.normalizacao.texto import so_letras_numeros

# País normalizado -> código ISO 3166 de 2 letras (nome, códigos ISO de 2 e 3 letras e sinônimos)
PAISES: dict[str, str] = {
    **dict.fromkeys(["CHINA", "PRC", "CN", "CHN", "P R CHINA", "PR CHINA", "PEOPLES REPUBLIC OF CHINA",
                     "PEOPLE S REPUBLIC OF CHINA", "REPUBLICA POPULAR DA CHINA"], "CN"),
    **dict.fromkeys(["KOREA", "SOUTH KOREA", "REPUBLIC OF KOREA", "KOREA REPUBLIC OF", "KR", "KOR",
                     "COREIA", "COREIA DO SUL", "COREA", "COREA DEL SUR", "ROK"], "KR"),
    **dict.fromkeys(["BRAZIL", "BRASIL", "BR", "BRA"], "BR"),
    **dict.fromkeys(["COLOMBIA", "CO", "COL"], "CO"),
    **dict.fromkeys(["USA", "US", "UNITED STATES", "UNITED STATES OF AMERICA", "ESTADOS UNIDOS", "EUA"], "US"),
    **dict.fromkeys(["INDIA", "IN", "IND"], "IN"),
    **dict.fromkeys(["JAPAN", "JAPAO", "JAPON", "JP", "JPN"], "JP"),
    **dict.fromkeys(["TAIWAN", "TW", "TWN", "CHINESE TAIPEI"], "TW"),
    **dict.fromkeys(["HONG KONG", "HK", "HKG"], "HK"),
    **dict.fromkeys(["VIETNAM", "VIET NAM", "VN", "VNM"], "VN"),
    **dict.fromkeys(["GERMANY", "ALEMANHA", "ALEMANIA", "DE", "DEU"], "DE"),
    **dict.fromkeys(["ITALY", "ITALIA", "IT", "ITA"], "IT"),
    **dict.fromkeys(["SPAIN", "ESPANHA", "ESPANA", "ES", "ESP"], "ES"),
    **dict.fromkeys(["NETHERLANDS", "HOLLAND", "HOLANDA", "PAISES BAIXOS", "PAISES BAJOS", "NL", "NLD"], "NL"),
    **dict.fromkeys(["BELGIUM", "BELGICA", "BELGIQUE", "BE", "BEL"], "BE"),
    **dict.fromkeys(["FRANCE", "FRANCA", "FRANCIA", "FR", "FRA"], "FR"),
    **dict.fromkeys(["PORTUGAL", "PT", "PRT"], "PT"),
    **dict.fromkeys(["UNITED KINGDOM", "UK", "GREAT BRITAIN", "REINO UNIDO", "GB", "GBR"], "GB"),
    **dict.fromkeys(["ARGENTINA", "AR", "ARG"], "AR"),
    **dict.fromkeys(["CHILE", "CL", "CHL"], "CL"),
    **dict.fromkeys(["MEXICO", "MX", "MEX"], "MX"),
    **dict.fromkeys(["PERU", "PE", "PER"], "PE"),
    **dict.fromkeys(["THAILAND", "TAILANDIA", "TH", "THA"], "TH"),
    **dict.fromkeys(["INDONESIA", "ID", "IDN"], "ID"),
    **dict.fromkeys(["MALAYSIA", "MALASIA", "MY", "MYS"], "MY"),
    **dict.fromkeys(["TURKEY", "TURKIYE", "TURQUIA", "TR", "TUR"], "TR"),
    **dict.fromkeys(["AUSTRIA", "AT", "AUT"], "AT"),
    **dict.fromkeys(["SWITZERLAND", "SUICA", "SUIZA", "CH", "CHE"], "CH"),
    **dict.fromkeys(["SWEDEN", "SUECIA", "SE", "SWE"], "SE"),
    **dict.fromkeys(["DENMARK", "DINAMARCA", "DK", "DNK"], "DK"),
    **dict.fromkeys(["FINLAND", "FINLANDIA", "FI", "FIN"], "FI"),
    **dict.fromkeys(["IRELAND", "IRLANDA", "IE", "IRL"], "IE"),
    **dict.fromkeys(["CZECH REPUBLIC", "CZECHIA", "REPUBLICA TCHECA", "CZ", "CZE"], "CZ"),
    **dict.fromkeys(["HUNGARY", "HUNGRIA", "HU", "HUN"], "HU"),
    **dict.fromkeys(["ROMANIA", "ROMENIA", "RO", "ROU"], "RO"),
    **dict.fromkeys(["GREECE", "GRECIA", "GR", "GRC"], "GR"),
    **dict.fromkeys(["SLOVAKIA", "ESLOVAQUIA", "SK", "SVK"], "SK"),
    **dict.fromkeys(["SLOVENIA", "ESLOVENIA", "SI", "SVN"], "SI"),
    **dict.fromkeys(["CANADA", "CA", "CAN"], "CA"),
    **dict.fromkeys(["AUSTRALIA", "AU", "AUS"], "AU"),
    **dict.fromkeys(["NEW ZEALAND", "NOVA ZELANDIA", "NZ", "NZL"], "NZ"),
    **dict.fromkeys(["URUGUAY", "URUGUAI", "UY", "URY"], "UY"),
    **dict.fromkeys(["PARAGUAY", "PARAGUAI", "PY", "PRY"], "PY"),
    **dict.fromkeys(["PAKISTAN", "PAQUISTAO", "PK", "PAK"], "PK"),
    **dict.fromkeys(["BANGLADESH", "BD", "BGD"], "BD"),
    **dict.fromkeys(["PHILIPPINES", "FILIPINAS", "PH", "PHL"], "PH"),
    **dict.fromkeys(["SINGAPORE", "SINGAPURA", "SG", "SGP"], "SG"),
    **dict.fromkeys(["ISRAEL", "IL", "ISR"], "IL"),
    **dict.fromkeys(["SOUTH AFRICA", "AFRICA DO SUL", "ZA", "ZAF"], "ZA"),
    **dict.fromkeys(["SRI LANKA", "LK", "LKA"], "LK"),
    **dict.fromkeys(["CAMBODIA", "CAMBOJA", "KH", "KHM"], "KH"),
    **dict.fromkeys(["UNITED ARAB EMIRATES", "EMIRADOS ARABES UNIDOS", "UAE", "AE", "ARE"], "AE"),
}


SIGLAS_PAISES = set(PAISES.values())


def normalizar_pais(pais: str) -> str:
    """'South Korea' / 'KR' / 'Republic of Korea' -> 'KR'; desconhecido -> texto normalizado."""
    chave = so_letras_numeros(pais)
    if chave.startswith("THE "):
        chave = chave[4:]
    return PAISES.get(chave, chave)
