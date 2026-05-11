from flask import Flask, request, jsonify, render_template, send_from_directory
import requests
from bs4 import BeautifulSoup
import time
import json
import math
import re
import os
from datetime import datetime

app = Flask(__name__)

SCRAPER_KEY = 'ba86d5e7b2d9d94398648abbf3144e9c'
SCRAPER_URL = 'https://api.scraperapi.com/'

HISTORIAL_FILE = 'historial.json'

EXCLUDE_WORDS = [
    'estrenar', 'a estrenar', 'pozo', 'emprendimiento', 'torre',
    'boutique', 'desde usd', 'preventa', 'en construcción',
    'entrega', 'brand new', 'nuevo emprendimiento', 'lanzamiento'
]

TIPO_SLUG_ZP = {'departamento': 'departamentos', 'casa': 'casas', 'ph': 'ph'}
TIPO_SLUG_AP = {'departamento': 'departamentos', 'casa': 'casas', 'ph': 'ph'}

AMB_SLUG_ZP = {
    '1': 'monoambiente', '2': '2-ambientes', '3': '3-ambientes',
    '4': '4-ambientes', '5': '5-ambientes', '6': '6-ambientes'
}

BARRIO_SLUG = {
    'Palermo': 'palermo', 'Belgrano': 'belgrano', 'Recoleta': 'recoleta',
    'Núñez': 'nunez', 'Saavedra': 'saavedra', 'Colegiales': 'colegiales',
    'Villa Urquiza': 'villa-urquiza', 'Villa Crespo': 'villa-crespo',
    'Caballito': 'caballito', 'Almagro': 'almagro', 'Chacarita': 'chacarita',
    'Devoto': 'devoto', 'Flores': 'flores', 'San Telmo': 'san-telmo',
    'Barrio Norte': 'barrio-norte', 'Retiro': 'retiro',
    'Puerto Madero': 'puerto-madero', 'Liniers': 'liniers',
    'Mataderos': 'mataderos', 'Villa del Parque': 'villa-del-parque',
    'Villa Pueyrredón': 'villa-pueyrredon', 'Boedo': 'boedo',
    'Parque Patricios': 'parque-patricios', 'La Boca': 'la-boca',
    'Balvanera': 'balvanera', 'Montserrat': 'montserrat',
    'San Nicolás': 'san-nicolas', 'Floresta': 'floresta',
    'Belgrano R': 'belgrano-r', 'Belgrano C': 'belgrano-c',
    'Palermo Soho': 'palermo-soho', 'Palermo Hollywood': 'palermo-hollywood',
    'Las Cañitas': 'las-canitas', 'Villa Ortúzar': 'villa-ortuza',
    'Coghlan': 'coghlan', 'Villa Devoto': 'villa-devoto',
    'Martínez': 'martinez', 'Olivos': 'olivos', 'La Lucila': 'la-lucila',
    'Acassuso': 'acassuso', 'Beccar': 'beccar', 'Boulogne': 'boulogne',
    'La Horqueta': 'la-horqueta', 'Villa Adelina': 'villa-adelina',
    'San Isidro centro': 'san-isidro', 'Florida': 'florida',
    'Florida Oeste': 'florida-oeste', 'Munro': 'munro',
    'Vicente López centro': 'vicente-lopez', 'Nordelta': 'nordelta',
    'Tigre centro': 'tigre', 'El Talar': 'el-talar',
    'Don Torcuato': 'don-torcuato', 'General Pacheco': 'general-pacheco',
    'Rincón de Milberg': 'rincon-de-milberg', 'Benavídez': 'benavidez',
    'Pilar centro': 'pilar', 'Del Viso': 'del-viso',
    'Ingeniero Maschwitz': 'ingeniero-maschwitz', 'Garín': 'garin',
    'Ramos Mejía': 'ramos-mejia', 'San Justo': 'san-justo',
    'Adrogué': 'adrogue', 'Burzaco': 'burzaco',
    'Monte Grande': 'monte-grande', 'Canning': 'canning',
    'Banfield': 'banfield', 'Temperley': 'temperley',
    'Lomas centro': 'lomas-de-zamora', 'Quilmes centro': 'quilmes',
    'Bernal': 'bernal', 'Wilde': 'wilde', 'Hudson': 'hudson',
    'Ranelagh': 'ranelagh', 'Castelar': 'castelar', 'Haedo': 'haedo',
    'Morón centro': 'moron', 'San Antonio de Padua': 'san-antonio-de-padua',
    'Los Polvorines': 'los-polvorines', 'Grand Bourg': 'grand-bourg',
}

ANTIGUEDAD_RANGES = {
    'a estrenar': (0, 1),
    '1 a 10 años': (0, 12),
    '10 a 20 años': (8, 22),
    '20 a 30 años': (18, 32),
    '30 a 40 años': (28, 42),
    '40 a 50 años': (38, 52),
    'más de 50 años': (48, 999),
}


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2*R*math.atan2(math.sqrt(a), math.sqrt(1-a))


def geocode(address):
    try:
        url = f"https://nominatim.openstreetmap.org/search"
        params = {'q': address + ', Argentina', 'format': 'json', 'countrycodes': 'ar', 'limit': 1}
        headers = {'User-Agent': 'TasadorInmuebles/1.0'}
        r = requests.get(url, params=params, headers=headers, timeout=5)
        data = r.json()
        if data:
            return float(data[0]['lat']), float(data[0]['lon'])
    except:
        pass
    return None


def scrape_page(url):
    try:
        r = requests.get(SCRAPER_URL, params={
            'api_key': SCRAPER_KEY,
            'url': url,
            'render': 'true'
        }, timeout=30)
        if r.status_code == 200:
            return r.text
    except:
        pass
    return None


def extract_antiguedad(text):
    patterns = [
        r'(\d+)\s*años?\s*de\s*antigüedad',
        r'antigüedad[:\s]+(\d+)\s*años?',
        r'(\d+)\s*años?\s*antigüedad',
        r'"(\d+)"\s*años?',
        r'>(\d+)\s*años?<',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            val = int(m.group(1))
            if 0 < val < 150:
                return val
    return None


def parse_price(text):
    text = text.replace('.', '').replace(',', '')
    m = re.search(r'USD\s*(\d+)', text, re.IGNORECASE)
    if m:
        val = int(m.group(1))
        if 10000 < val < 50000000:
            return val
    return None


def parse_m2(text):
    m = re.search(r'(\d+)\s*m[²2]', text)
    if m:
        val = int(m.group(1))
        if 10 < val < 5000:
            return val
    return None


def scrape_zonaprop(tipo, operacion, localidad, ambientes, es_usado):
    tipo_slug = TIPO_SLUG_ZP.get(tipo, 'departamentos')
    op_slug = 'venta' if operacion == 'venta' else 'alquiler'
    loc_slug = BARRIO_SLUG.get(localidad, localidad.lower().replace(' ', '-'))
    amb_slug = AMB_SLUG_ZP.get(ambientes, f'{ambientes}-ambientes')
    usado_slug = '-usado' if es_usado else ''

    listings = []
    page = 1

    while page <= 20:
        if page == 1:
            url = f"https://www.zonaprop.com.ar/{tipo_slug}-{op_slug}-{loc_slug}-{amb_slug}{usado_slug}.html"
        else:
            url = f"https://www.zonaprop.com.ar/{tipo_slug}-{op_slug}-{loc_slug}-{amb_slug}{usado_slug}-pagina-{page}.html"

        html = scrape_page(url)
        if not html:
            break

        soup = BeautifulSoup(html, 'html.parser')
        cards = soup.find_all(['div', 'article'], attrs={'data-id': True})

        if not cards:
            cards = soup.find_all('div', class_=re.compile(r'posting|card|listing', re.I))

        if not cards:
            break

        new_found = 0
        for card in cards:
            text = card.get_text(' ', strip=True)
            price = parse_price(text)
            if not price:
                continue

            m2_cub = None
            m2_tot = None
            m2_matches = re.findall(r'(\d+)\s*m[²2]', text)
            for val in m2_matches:
                v = int(val)
                if 10 < v < 5000:
                    if m2_cub is None:
                        m2_cub = v
                    elif m2_tot is None:
                        m2_tot = v
                        break

            antiguedad = extract_antiguedad(text)
            addr_el = card.find(class_=re.compile(r'address|location|direction', re.I))
            address = addr_el.get_text(strip=True) if addr_el else ''

            title_el = card.find(['h2', 'h3', 'a'], class_=re.compile(r'title|name', re.I))
            title = title_el.get_text(strip=True) if title_el else text[:80]

            listings.append({
                'title': title,
                'address': address,
                'm2_cubiertos': m2_cub,
                'm2_totales': m2_tot,
                'antiguedad': antiguedad,
                'precio': price,
                'usd_m2': round(price / m2_cub) if m2_cub else None,
                'fuente': 'ZonaProp'
            })
            new_found += 1

        if new_found == 0:
            break

        page += 1
        time.sleep(0.5)

    return listings


def scrape_argenprop(tipo, operacion, localidad, ambientes, es_usado):
    tipo_slug = TIPO_SLUG_AP.get(tipo, 'departamentos')
    op_slug = 'venta' if operacion == 'venta' else 'alquiler'
    loc_slug = BARRIO_SLUG.get(localidad, localidad.lower().replace(' ', '-'))
    amb_num = ambientes
    amb_slug = 'monoambiente' if ambientes == '1' else f'{amb_num}-ambientes'

    listings = []
    page = 1

    while page <= 20:
        if page == 1:
            url = f"https://www.argenprop.com/{tipo_slug}/{op_slug}/{loc_slug}/{amb_slug}"
        else:
            url = f"https://www.argenprop.com/{tipo_slug}/{op_slug}/{loc_slug}/{amb_slug}?pagina={page}"

        html = scrape_page(url)
        if not html:
            break

        soup = BeautifulSoup(html, 'html.parser')
        cards = soup.find_all(['div', 'article'], class_=re.compile(r'card|listing|property|prop', re.I))

        if not cards:
            break

        new_found = 0
        for card in cards:
            text = card.get_text(' ', strip=True)
            price = parse_price(text)
            if not price:
                continue

            m2_cub = None
            m2_tot = None
            m2_matches = re.findall(r'(\d+)\s*m[²2]', text)
            for val in m2_matches:
                v = int(val)
                if 10 < v < 5000:
                    if m2_cub is None:
                        m2_cub = v
                    elif m2_tot is None:
                        m2_tot = v
                        break

            antiguedad = extract_antiguedad(text)
            addr_el = card.find(class_=re.compile(r'address|location|direction', re.I))
            address = addr_el.get_text(strip=True) if addr_el else ''

            title_el = card.find(['h2', 'h3', 'a'])
            title = title_el.get_text(strip=True) if title_el else text[:80]

            listings.append({
                'title': title,
                'address': address,
                'm2_cubiertos': m2_cub,
                'm2_totales': m2_tot,
                'antiguedad': antiguedad,
                'precio': price,
                'usd_m2': round(price / m2_cub) if m2_cub else None,
                'fuente': 'Argenprop'
            })
            new_found += 1

        if new_found == 0:
            break

        page += 1
        time.sleep(0.5)

    return listings


def filter_listings(listings, tipo, m2_objetivo, antiguedad_sel, es_usado, ref_coords, localidad):
    stats = {
        'total': len(listings),
        'excluidos_nuevos': 0,
        'excluidos_m2': 0,
        'excluidos_antiguedad': 0,
        'excluidos_distancia': 0,
        'radio_usado': None,
    }

    # 1. Deduplicar
    seen = set()
    deduped = []
    for l in listings:
        key = (l.get('address', '')[:30], l.get('precio'))
        if key not in seen:
            seen.add(key)
            deduped.append(l)
    listings = deduped

    # 2. Excluir nuevos si es usado
    if es_usado:
        filtered = []
        for l in listings:
            title_lower = (l.get('title', '') + ' ' + l.get('address', '')).lower()
            if any(w in title_lower for w in EXCLUDE_WORDS):
                stats['excluidos_nuevos'] += 1
            else:
                filtered.append(l)
        listings = filtered

    # 3. Filtro m² cubiertos
    if m2_objetivo:
        m2_obj = int(m2_objetivo)
        if tipo == 'casa':
            if m2_obj <= 50: pct = 0.20
            elif m2_obj <= 100: pct = 0.22
            elif m2_obj <= 200: pct = 0.25
            else: pct = 0.30
        else:
            if m2_obj <= 50: pct = 0.15
            elif m2_obj <= 100: pct = 0.20
            elif m2_obj <= 200: pct = 0.25
            else: pct = 0.30

        m2_min = m2_obj * (1 - pct)
        m2_max = m2_obj * (1 + pct)
        filtered = []
        for l in listings:
            m2 = l.get('m2_cubiertos')
            if m2 is None or (m2_min <= m2 <= m2_max):
                filtered.append(l)
            else:
                stats['excluidos_m2'] += 1
        listings = filtered

    # 4. Filtro antigüedad
    ant_range = ANTIGUEDAD_RANGES.get(antiguedad_sel)
    if ant_range and antiguedad_sel != 'a estrenar':
        ant_min, ant_max = ant_range
        filtered = []
        for l in listings:
            ant = l.get('antiguedad')
            if ant is None or (ant_min <= ant <= ant_max):
                filtered.append(l)
            else:
                stats['excluidos_antiguedad'] += 1
        listings = filtered

        # Si quedan menos de 4, relajar ±5 años
        if len(listings) < 4:
            ant_min2, ant_max2 = ant_min - 5, ant_max + 5
            extra = []
            for l in deduped:
                ant = l.get('antiguedad')
                if ant and (ant_min2 <= ant <= ant_max2) and l not in listings:
                    extra.append(l)
            listings = listings + extra[:max(0, 4 - len(listings))]

    # 5. Filtro distancia
    if ref_coords:
        radios = [800, 1500, 2500]
        for radio in radios:
            con_distancia = []
            sin_coords = []
            for l in listings:
                addr = l.get('address', '')
                if addr:
                    coords = geocode(f"{addr}, {localidad}, Buenos Aires")
                    if coords:
                        dist = haversine(ref_coords[0], ref_coords[1], coords[0], coords[1])
                        l['distancia_m'] = round(dist)
                        if dist <= radio:
                            con_distancia.append(l)
                        else:
                            stats['excluidos_distancia'] += 1
                    else:
                        sin_coords.append(l)
                else:
                    sin_coords.append(l)
                time.sleep(0.2)

            if len(con_distancia) >= 4:
                stats['radio_usado'] = radio
                listings = con_distancia
                break
        else:
            stats['radio_usado'] = 'barrio completo'
    
    stats['finales'] = len(listings)
    return listings, stats


def calcular_precio_equivalente(m2_cubiertos, amenities):
    m2_eq = float(m2_cubiertos) if m2_cubiertos else 0

    # Balcón / terraza al 50%
    if amenities.get('balcon_m2'):
        m2_eq += float(amenities['balcon_m2']) * 0.5
    if amenities.get('terraza_m2'):
        m2_eq += float(amenities['terraza_m2']) * 0.5

    # Jardín — regla Toribio Achával
    if amenities.get('jardin_m2'):
        jardin = float(amenities['jardin_m2'])
        pct_jardin = jardin / m2_cubiertos if m2_cubiertos else 0
        if pct_jardin <= 0.12:
            m2_eq += jardin * 1.0
        elif pct_jardin <= 0.22:
            m2_eq += jardin * 0.5
        else:
            m2_eq += jardin * 0.25

    return m2_eq


def calcular_tasacion(listings, m2_cubiertos, amenities):
    if not listings:
        return None

    # Mediana USD/m²
    precios_m2 = [l['usd_m2'] for l in listings if l.get('usd_m2')]
    precios = [l['precio'] for l in listings if l.get('precio')]

    if not precios:
        return None

    precios.sort()
    precios_m2.sort() if precios_m2 else None

    def mediana(lst):
        n = len(lst)
        if n == 0: return None
        mid = n // 2
        return lst[mid] if n % 2 else (lst[mid-1] + lst[mid]) // 2

    med_precio = mediana(precios)
    med_m2 = mediana(precios_m2) if precios_m2 else None

    # Calcular precio por m² equivalente
    if med_m2 and m2_cubiertos:
        m2_eq = calcular_precio_equivalente(int(m2_cubiertos), amenities)
        precio_base = round(med_m2 * m2_eq)
    else:
        precio_base = med_precio

    # Ajustes amenities (%)
    ajuste = 1.0
    if amenities.get('cochera'): ajuste += 0.08
    if amenities.get('pileta'): ajuste += 0.10
    if amenities.get('quincho'): ajuste += 0.03
    if amenities.get('baulera'): ajuste += 0.02
    if amenities.get('gym'): ajuste += 0.02
    if amenities.get('sum'): ajuste += 0.02
    if amenities.get('seguridad'): ajuste += 0.02

    precio_ajustado = round(precio_base * ajuste)

    return {
        'mediana_precio': med_precio,
        'min_precio': precios[0],
        'max_precio': precios[-1],
        'mediana_m2': med_m2,
        'precio_publicacion': round(precio_ajustado * 1.05 / 1000) * 1000,
        'precio_cierre': round(precio_ajustado / 1000) * 1000,
        'precio_piso': round(precio_ajustado * 0.96 / 1000) * 1000,
        'margen': '4-5%',
    }


def cargar_historial():
    if os.path.exists(HISTORIAL_FILE):
        with open(HISTORIAL_FILE, 'r') as f:
            return json.load(f)
    return []


def guardar_historial(entry):
    historial = cargar_historial()
    historial.insert(0, entry)
    historial = historial[:50]
    with open(HISTORIAL_FILE, 'w') as f:
        json.dump(historial, f, ensure_ascii=False, indent=2)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/historial')
def get_historial():
    return jsonify(cargar_historial())


@app.route('/api/tasar', methods=['POST'])
def tasar():
    data = request.json

    tipo = data.get('tipo', 'departamento')
    operacion = data.get('operacion', 'venta')
    localidad = data.get('localidad', '')
    referencia = data.get('referencia', '')
    ambientes = data.get('ambientes', '2')
    m2_cubiertos = data.get('m2_cubiertos')
    antiguedad_sel = data.get('antiguedad', '10 a 20 años')
    amenities = data.get('amenities', {})

    es_usado = antiguedad_sel != 'a estrenar'

    # Geocodificar referencia
    ref_coords = None
    if referencia:
        query = f"{referencia}, {localidad}, Buenos Aires"
        ref_coords = geocode(query)

    # Scraping
    zp_listings = scrape_zonaprop(tipo, operacion, localidad, ambientes, es_usado)
    ap_listings = scrape_argenprop(tipo, operacion, localidad, ambientes, es_usado)
    all_listings = zp_listings + ap_listings

    # Filtros
    filtered, stats = filter_listings(
        all_listings, tipo, m2_cubiertos, antiguedad_sel,
        es_usado, ref_coords, localidad
    )

    # Tasación
    tasacion = calcular_tasacion(filtered, m2_cubiertos, amenities)

    # Guardar historial
    if tasacion:
        entry = {
            'id': datetime.now().isoformat(),
            'fecha': datetime.now().strftime('%d/%m/%Y'),
            'tipo': tipo,
            'localidad': localidad,
            'ambientes': ambientes,
            'm2_cubiertos': m2_cubiertos,
            'antiguedad': antiguedad_sel,
            'precio_publicacion': tasacion['precio_publicacion'],
            'comparables': len(filtered),
        }
        guardar_historial(entry)

    return jsonify({
        'listings': filtered[:15],
        'stats': stats,
        'tasacion': tasacion,
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)
