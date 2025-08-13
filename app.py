#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime
import logging

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static')
CORS(app)

# Konfiguracja bazy danych SQLite - automatyczne wyszukiwanie
def find_database():
    """Automatycznie znajduje plik bazy danych SQLite"""
    possible_names = [
        'sqlite',           # bez rozszerzenia
        'sqlite.db',        # z rozszerzeniem .db
        'sqlite.sqlite',    # z rozszerzeniem .sqlite
        'sqlite.sqlite3',   # z rozszerzeniem .sqlite3
        'conference.db',    # alternatywne nazwy
        'companies.db',
        'database.db',
        'db.sqlite3',
        'database.sqlite'
    ]
    
    current_dir = os.getcwd()
    logger.info(f"Szukam bazy danych w folderze: {current_dir}")
    
    # Sprawdź wszystkie pliki w folderze
    all_files = os.listdir('.')
    logger.info(f"Pliki w folderze: {all_files}")
    
    # Sprawdź czy istnieją typowe pliki SQLite
    sqlite_files = [f for f in all_files if f.endswith(('.db', '.sqlite', '.sqlite3')) or f == 'sqlite']
    if sqlite_files:
        logger.info(f"Znalezione pliki bazy danych: {sqlite_files}")
    
    # Sprawdź czy któryś z możliwych plików istnieje
    for db_name in possible_names:
        if os.path.exists(db_name):
            logger.info(f"✅ Znaleziono bazę danych: {db_name}")
            return db_name
    
    # Jeśli nie znaleziono, sprawdź pierwszy plik .db/.sqlite
    for file in sqlite_files:
        if os.path.exists(file):
            logger.info(f"🔍 Próbuję użyć pliku: {file}")
            return file
    
    logger.error("❌ Nie znaleziono żadnego pliku bazy danych!")
    logger.info("💡 Możliwe rozwiązania:")
    logger.info("   1. Umieść plik bazy w folderze z app.py")
    logger.info("   2. Nazwa pliku powinna być 'sqlite' lub mieć rozszerzenie .db/.sqlite/.sqlite3")
    logger.info("   3. Sprawdź czy plik nie jest w innym folderze")
    return None

DATABASE_PATH = find_database() or 'sqlite'  # Fallback do 'sqlite'

# Port serwera
PORT = 3000

def get_db_connection():
    """Tworzy połączenie z bazą danych SQLite"""
    try:
        if not os.path.exists(DATABASE_PATH):
            logger.error(f"Plik bazy danych {DATABASE_PATH} nie istnieje!")
            return None
            
        connection = sqlite3.connect(DATABASE_PATH)
        connection.row_factory = sqlite3.Row  # Pozwala na dostęp do kolumn po nazwie
        return connection
    except Exception as e:
        logger.error(f"Błąd połączenia z bazą danych: {e}")
        return None

def init_database():
    """Sprawdza strukturę bazy danych"""
    try:
        if not DATABASE_PATH:
            logger.error("Nie znaleziono pliku bazy danych!")
            return False
            
        if not os.path.exists(DATABASE_PATH):
            logger.error(f"Plik bazy danych {DATABASE_PATH} nie istnieje!")
            return False
            
        logger.info(f"🔗 Łączę się z bazą: {DATABASE_PATH}")
        connection = get_db_connection()
        if not connection:
            logger.error("Nie można połączyć się z bazą danych")
            return False
            
        cursor = connection.cursor()
        
        # Sprawdzenie czy tabela companies istnieje
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='companies'
        """)
        
        table_exists = cursor.fetchone()
        
        if table_exists:
            # Sprawdzenie struktury tabeli
            cursor.execute("PRAGMA table_info(companies)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            logger.info(f"Znaleziono tabelę 'companies' z kolumnami: {column_names}")
            
            # Sprawdzenie liczby rekordów
            cursor.execute("SELECT COUNT(*) FROM companies")
            count = cursor.fetchone()[0]
            logger.info(f"W bazie znajduje się {count} firm")
            
        else:
            logger.warning("Tabela 'companies' nie istnieje w bazie danych")
            logger.info("Spróbuję wyświetlić wszystkie tabele w bazie:")
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            for table in tables:
                logger.info(f"  - {table[0]}")
        
        cursor.close()
        connection.close()
        return True
        
    except Exception as e:
        logger.error(f"Błąd podczas sprawdzania bazy danych: {e}")
        return False

def transform_company_data(row):
    """Przekształca dane z bazy do formatu zgodnego z frontendem"""
    # Konwersja sqlite3.Row do dict
    row_dict = dict(row)
    
    hooks = []
    for hook_key in ['zaczepka1', 'zaczepka2', 'zaczepka3']:
        hook_value = row_dict.get(hook_key)
        if hook_value and str(hook_value).strip():
            hooks.append(str(hook_value).strip())
    
    # Pobierz wartość rarity bezpośrednio z kolumny czy_warto_sie_zainteresowac
    priority_value = row_dict.get('czy_warto_sie_zainteresowac')
    rarity = 0  # domyślnie
    
    if priority_value is not None:
        try:
            # Konwertuj na int - wartości 0, 1, 2 odpowiadają poziomom rarity
            rarity = int(priority_value)
            # Upewnij się, że wartość jest w dozwolonym zakresie
            if rarity not in [0, 1, 2]:
                rarity = 0
        except (ValueError, TypeError):
            # Jeśli nie da się skonwertować na int, zostaw 0
            rarity = 0
    
    return {
        'id': row_dict.get('id'),
        'name': row_dict.get('company', ''),
        'boothNumber': row_dict.get('stand', ''),
        'country': row_dict.get('country', ''),
        'positions': ["Sprawdź na miejscu"],
        'shortDescription': (row_dict.get('czym_zajmuje_sie_firma', '')[:100] + '...' 
                           if row_dict.get('czym_zajmuje_sie_firma') and len(str(row_dict.get('czym_zajmuje_sie_firma'))) > 100 
                           else row_dict.get('czym_zajmuje_sie_firma', '') or 'Sprawdź szczegóły'),
        'description': row_dict.get('czym_zajmuje_sie_firma', ''),
        'problems': row_dict.get('problemy_i_wyzwania', ''),
        'opportunities': row_dict.get('mozliwosci_AI_i_danych', ''),
        'rarity': rarity,  # Teraz poprawnie używa wartości 0, 1, 2 z bazy
        'hooks': hooks
    }

# ROUTES

@app.route('/')
def serve_frontend():
    """Serwuje frontend"""
    return send_from_directory('static', 'index.html')

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serwuje pliki statyczne"""
    return send_from_directory('static', filename)

@app.route('/api/test', methods=['GET'])
def test_connection():
    """Test połączenia z bazą danych"""
    try:
        if not os.path.exists(DATABASE_PATH):
            return jsonify({
                'status': 'error',
                'message': f'Plik bazy danych {DATABASE_PATH} nie istnieje',
                'database_path': DATABASE_PATH
            }), 500
            
        connection = get_db_connection()
        if not connection:
            return jsonify({
                'status': 'error',
                'message': 'Nie można połączyć się z bazą danych',
                'database_path': DATABASE_PATH
            }), 500
        
        cursor = connection.cursor()
        
        # Sprawdzenie czy tabela companies istnieje
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='companies'
        """)
        table_exists = cursor.fetchone()
        
        if not table_exists:
            # Pokaż dostępne tabele
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            cursor.close()
            connection.close()
            
            return jsonify({
                'status': 'warning',
                'message': 'Tabela companies nie istnieje',
                'database_path': DATABASE_PATH,
                'available_tables': tables,
                'timestamp': datetime.now().isoformat()
            }), 200
        
        # Sprawdzenie struktury tabeli
        cursor.execute("PRAGMA table_info(companies)")
        columns = [{'name': col[1], 'type': col[2]} for col in cursor.fetchall()]
        
        # Liczba rekordów
        cursor.execute("SELECT COUNT(*) FROM companies")
        count = cursor.fetchone()[0]
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'status': 'success',
            'message': 'Połączenie z bazą danych działa!',
            'database_path': DATABASE_PATH,
            'table_structure': columns,
            'companies_count': count,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Błąd podczas testu połączenia: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Błąd bazy danych: {str(e)}',
            'database_path': DATABASE_PATH
        }), 500

@app.route('/api/companies', methods=['GET'])
def get_companies():
    """Pobiera wszystkie firmy z możliwością filtrowania"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Błąd połączenia z bazą danych'}), 500
        
        cursor = connection.cursor()
        
        # Parametry wyszukiwania
        search = request.args.get('search', '').strip()
        search_by = request.args.get('searchBy', 'company')
        priority = request.args.get('priority', '')
        
        # Budowanie zapytania
        query = "SELECT * FROM companies"
        params = []
        conditions = []
        
        # Wyszukiwanie
        if search:
            if search_by == 'company':
                conditions.append("company LIKE ?")
                params.append(f"%{search}%")
            elif search_by == 'stand':
                conditions.append("stand LIKE ?")
                params.append(f"%{search}%")
        
        # Filtrowanie po priorytecie
        if priority:
            # Obsługa różnych formatów wartości priorytetu
            if priority.lower() in ['tak', 'yes', '1', 'true', 'warto']:
                conditions.append("(czy_warto_sie_zainteresowac = '1' OR czy_warto_sie_zainteresowac = 'tak' OR czy_warto_sie_zainteresowac = 'yes')")
            elif priority.lower() in ['nie', 'no', '0', 'false']:
                conditions.append("(czy_warto_sie_zainteresowac = '0' OR czy_warto_sie_zainteresowac = 'nie' OR czy_warto_sie_zainteresowac = 'no')")
            else:
                conditions.append("czy_warto_sie_zainteresowac = ?")
                params.append(priority)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY company ASC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # Transformacja danych
        companies = [transform_company_data(row) for row in rows]
        
        cursor.close()
        connection.close()
        
        return jsonify(companies)
        
    except Exception as e:
        logger.error(f"Błąd podczas pobierania firm: {e}")
        return jsonify({'error': f'Błąd serwera: {str(e)}'}), 500

@app.route('/api/companies/<int:company_id>', methods=['GET'])
def get_company(company_id):
    """Pobiera jedną firmę po ID"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Błąd połączenia z bazą danych'}), 500
        
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM companies WHERE id = ?", (company_id,))
        row = cursor.fetchone()
        
        if not row:
            cursor.close()
            connection.close()
            return jsonify({'error': 'Firma nie została znaleziona'}), 404
        
        company = transform_company_data(row)
        
        cursor.close()
        connection.close()
        
        return jsonify(company)
        
    except Exception as e:
        logger.error(f"Błąd podczas pobierania firmy: {e}")
        return jsonify({'error': f'Błąd serwera: {str(e)}'}), 500

@app.route('/api/companies', methods=['POST'])
def add_company():
    """Dodaje nową firmę"""
    try:
        data = request.get_json()
        
        if not data or not data.get('company'):
            return jsonify({'error': 'Nazwa firmy jest wymagana'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Błąd połączenia z bazą danych'}), 500
        
        cursor = connection.cursor()
        
        insert_query = """
        INSERT INTO companies (company, country, stand, czym_zajmuje_sie_firma, 
            problemy_i_wyzwania, mozliwosci_AI_i_danych, zaczepka1, zaczepka2, 
            zaczepka3, czy_warto_sie_zainteresowac) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        params = (
            data.get('company'),
            data.get('country'),
            data.get('stand'),
            data.get('czym_zajmuje_sie_firma'),
            data.get('problemy_i_wyzwania'),
            data.get('mozliwosci_AI_i_danych'),
            data.get('zaczepka1'),
            data.get('zaczepka2'),
            data.get('zaczepka3'),
            data.get('czy_warto_sie_zainteresowac', 0)
        )
        
        cursor.execute(insert_query, params)
        connection.commit()
        
        company_id = cursor.lastrowid
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'message': 'Firma została dodana',
            'id': company_id
        }), 201
        
    except Exception as e:
        logger.error(f"Błąd podczas dodawania firmy: {e}")
        return jsonify({'error': f'Błąd serwera: {str(e)}'}), 500

@app.route('/api/companies/<int:company_id>', methods=['PUT'])
def update_company(company_id):
    """Aktualizuje firmę"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Brak danych do aktualizacji'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Błąd połączenia z bazą danych'}), 500
        
        cursor = connection.cursor()
        
        update_query = """
        UPDATE companies SET 
            company = ?, country = ?, stand = ?, czym_zajmuje_sie_firma = ?,
            problemy_i_wyzwania = ?, mozliwosci_AI_i_danych = ?, zaczepka1 = ?,
            zaczepka2 = ?, zaczepka3 = ?, czy_warto_sie_zainteresowac = ?
        WHERE id = ?
        """
        
        params = (
            data.get('company'),
            data.get('country'),
            data.get('stand'),
            data.get('czym_zajmuje_sie_firma'),
            data.get('problemy_i_wyzwania'),
            data.get('mozliwosci_AI_i_danych'),
            data.get('zaczepka1'),
            data.get('zaczepka2'),
            data.get('zaczepka3'),
            data.get('czy_warto_sie_zainteresowac'),
            company_id
        )
        
        cursor.execute(update_query, params)
        connection.commit()
        
        if cursor.rowcount == 0:
            cursor.close()
            connection.close()
            return jsonify({'error': 'Firma nie została znaleziona'}), 404
        
        cursor.close()
        connection.close()
        
        return jsonify({'message': 'Firma została zaktualizowana'})
        
    except Exception as e:
        logger.error(f"Błąd podczas aktualizacji firmy: {e}")
        return jsonify({'error': f'Błąd serwera: {str(e)}'}), 500

@app.route('/api/companies/<int:company_id>', methods=['DELETE'])
def delete_company(company_id):
    """Usuwa firmę"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Błąd połączenia z bazą danych'}), 500
        
        cursor = connection.cursor()
        cursor.execute("DELETE FROM companies WHERE id = ?", (company_id,))
        connection.commit()
        
        if cursor.rowcount == 0:
            cursor.close()
            connection.close()
            return jsonify({'error': 'Firma nie została znaleziona'}), 404
        
        cursor.close()
        connection.close()
        
        return jsonify({'message': 'Firma została usunięta'})
        
    except Exception as e:
        logger.error(f"Błąd podczas usuwania firmy: {e}")
        return jsonify({'error': f'Błąd serwera: {str(e)}'}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Pobiera statystyki firm"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Błąd połączenia z bazą danych'}), 500
        
        cursor = connection.cursor()
        
        # Całkowita liczba firm
        cursor.execute("SELECT COUNT(*) FROM companies")
        total = cursor.fetchone()[0]
        
        # Statystyki według priorytetu
        cursor.execute("""
            SELECT czy_warto_sie_zainteresowac as priority, COUNT(*) as count 
            FROM companies 
            GROUP BY czy_warto_sie_zainteresowac
        """)
        priority_stats = [{'priority': row[0], 'count': row[1]} for row in cursor.fetchall()]
        
        # Statystyki według kraju
        cursor.execute("""
            SELECT country, COUNT(*) as count 
            FROM companies 
            WHERE country IS NOT NULL AND country != ''
            GROUP BY country 
            ORDER BY count DESC
        """)
        country_stats = [{'country': row[0], 'count': row[1]} for row in cursor.fetchall()]
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'total': total,
            'byPriority': priority_stats,
            'byCountry': country_stats
        })
        
    except Exception as e:
        logger.error(f"Błąd podczas pobierania statystyk: {e}")
        return jsonify({'error': f'Błąd serwera: {str(e)}'}), 500

@app.route('/api/debug/priority-values', methods=['GET'])
def debug_priority_values():
    """Debug: sprawdza jakie wartości są w kolumnie czy_warto_sie_zainteresowac"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Błąd połączenia z bazą danych'}), 500
        
        cursor = connection.cursor()
        
        # Sprawdź unikalne wartości w kolumnie priority
        cursor.execute("""
            SELECT czy_warto_sie_zainteresowac, COUNT(*) as count 
            FROM companies 
            GROUP BY czy_warto_sie_zainteresowac
            ORDER BY count DESC
        """)
        priority_values = [{'value': row[0], 'count': row[1]} for row in cursor.fetchall()]
        
        # Sprawdź strukturę tabeli
        cursor.execute("PRAGMA table_info(companies)")
        columns = [{'name': col[1], 'type': col[2]} for col in cursor.fetchall()]
        
        # Sprawdź przykładowe rekordy
        cursor.execute("SELECT id, company, czy_warto_sie_zainteresowac FROM companies LIMIT 10")
        sample_records = [dict(row) for row in cursor.fetchall()]
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'priority_values': priority_values,
            'table_columns': columns,
            'sample_records': sample_records
        })
        
    except Exception as e:
        logger.error(f"Błąd podczas debug priority values: {e}")
        return jsonify({'error': f'Błąd serwera: {str(e)}'}), 500

@app.route('/api/tables', methods=['GET'])
def get_tables():
    """Pokazuje wszystkie tabele w bazie danych (pomocne przy debugowaniu)"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Błąd połączenia z bazą danych'}), 500
        
        cursor = connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'tables': tables,
            'database_path': DATABASE_PATH
        })
        
    except Exception as e:
        logger.error(f"Błąd podczas pobierania tabel: {e}")
        return jsonify({'error': f'Błąd serwera: {str(e)}'}), 500

@app.errorhandler(404)
def not_found(error):
    """Handler dla 404"""
    return jsonify({'error': 'Endpoint nie został znaleziony'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handler dla błędów serwera"""
    return jsonify({'error': 'Błąd wewnętrzny serwera'}), 500

if __name__ == '__main__':
    print("🚀 Uruchamianie serwera Conference Companies API...")
    
    # Znajdź bazę danych
    DATABASE_PATH = find_database()
    
    if DATABASE_PATH:
        print(f"📊 Znaleziona baza danych: {DATABASE_PATH}")
        
        # Sprawdzenie bazy danych
        if init_database():
            print(f"🌐 Serwer będzie dostępny pod adresem: http://localhost:{PORT}")
            print(f"🎨 Frontend: http://localhost:{PORT}")
            print(f"🔗 API: http://localhost:{PORT}/api/companies")
            print(f"🧪 Test połączenia: http://localhost:{PORT}/api/test")
            print("📁 Umieść plik index.html w folderze 'static/'")
            print("\n✅ Serwer uruchomiony! Naciśnij Ctrl+C aby zatrzymać.")
            
            # Uruchomienie serwera
            app.run(host='0.0.0.0', port=PORT, debug=True)
        else:
            print("❌ Nie można uruchomić serwera - problemy z bazą danych")
    else:
        print("❌ Nie znaleziono pliku bazy danych!")
        print("💡 Sprawdź czy masz plik bazy w folderze:")
        print("   - sqlite")
        print("   - sqlite.db") 
        print("   - database.sqlite")
        print("   - lub inny plik .db/.sqlite/.sqlite3")