"""
CLI интерфейс для подключения к MS Project Server
Позволяет вводить параметры подключения через терминал
"""
import getpass
from server_connection import MSProjectServerConnection
from server_data_loader import MSProjectServerDataLoader

# Константы подключения по умолчанию
DEFAULT_SERVER_URL = "http://tpch-app04/Projects.aspx"
DEFAULT_DOMAIN = "TECHPROM"


def input_connection_params():
    """
    Запрашивает параметры подключения у пользователя через терминал
    
    Returns:
        tuple: (server_url, username, password, domain) или None при отмене
    """
    print("\n=== Ввод параметров подключения ===")
    
    # Запрос URL сервера с значением по умолчанию
    server_url = input(f"URL сервера [{DEFAULT_SERVER_URL}]: ").strip()
    if not server_url:
        server_url = DEFAULT_SERVER_URL
    
    # Запрос имени пользователя
    username = input("Имя пользователя: ").strip()
    if not username:
        print("❌ Имя пользователя не может быть пустым")
        return None
    
    # Запрос пароля (скрытый ввод)
    password = getpass.getpass("Пароль: ")
    if not password:
        print("❌ Пароль не может быть пустым")
        return None
    
    # Запрос домена с значением по умолчанию
    domain = input(f"Домен [{DEFAULT_DOMAIN}]: ").strip()
    if not domain:
        domain = DEFAULT_DOMAIN
    
    return (server_url, username, password, domain)


def print_status(connection):
    """
    Выводит текущий статус подключения
    
    Args:
        connection: Экземпляр MSProjectServerConnection
    """
    if connection.is_connected():
        server_url = connection.get_server_url()
        print(f"\n✓ Статус: Подключено к {server_url}")
    else:
        print("\n○ Статус: Не подключено")


def main():
    """
    Главная функция с интерактивным меню
    """
    connection = MSProjectServerConnection()
    
    while True:
        print("\n" + "=" * 50)
        print("=== Подключение к MS Project Server ===")
        print("=" * 50)
        print("1. Подключиться")
        print("2. Отключиться")
        print("3. Проверить статус")
        print("4. Выход")
        print("=" * 50)
        
        choice = input("\nВыберите действие (1-4): ").strip()
        
        if choice == "1":
            # Подключение
            if connection.is_connected():
                print("\n⚠️  Уже подключено к серверу.")
                print_status(connection)
                print("Сначала выполните отключение (пункт 2)")
            else:
                params = input_connection_params()
                if params:
                    server_url, username, password, domain = params
                    print("\n⏳ Попытка подключения...")
                    success = connection.connect(server_url, username, password, domain)
                    if success:
                        print("\n✓ Успешно подключено!")
                        print_status(connection)
                        
                        # Создание загрузчика данных
                        data_loader = MSProjectServerDataLoader(connection)
                        
                        # Загрузка и вывод проектов
                        try:
                            print("\n⏳ Загрузка проектов...")
                            projects = data_loader.load_projects()
                            
                            if projects:
                                print(f"\n📋 Проекты ({len(projects)}):")
                                for project in projects:
                                    project_name = project.get('Name', project.get('ProjectName', 'Без названия'))
                                    print(f"  - {project_name}")
                            else:
                                print("\n⚠️  Проекты не найдены или произошла ошибка при загрузке")
                        except Exception as e:
                            print(f"\n❌ Ошибка при загрузке проектов: {str(e)}")
                        
                        # Загрузка и вывод ресурсов
                        try:
                            print("\n⏳ Загрузка ресурсов...")
                            resources = data_loader.load_resources()
                            
                            if resources:
                                print(f"\n👥 Ресурсы ({len(resources)}):")
                                for resource in resources:
                                    resource_name = resource.get('Name', resource.get('ResourceName', 'Без названия'))
                                    print(f"  - {resource_name}")
                            else:
                                print("\n⚠️  Ресурсы не найдены или произошла ошибка при загрузке")
                        except Exception as e:
                            print(f"\n❌ Ошибка при загрузке ресурсов: {str(e)}")
                    else:
                        print("\n❌ Не удалось подключиться. Проверьте логи выше.")
        
        elif choice == "2":
            # Отключение
            if connection.is_connected():
                print("\n⏳ Отключение...")
                connection.disconnect()
                print("✓ Отключено от сервера")
            else:
                print("\n⚠️  Не подключено. Нет активного соединения для отключения.")
        
        elif choice == "3":
            # Проверка статуса
            print_status(connection)
        
        elif choice == "4":
            # Выход
            if connection.is_connected():
                print("\n⚠️  Активное подключение обнаружено.")
                confirm = input("Отключиться перед выходом? (y/n): ").strip().lower()
                if confirm == "y":
                    connection.disconnect()
                    print("✓ Отключено")
            print("\n👋 До свидания!")
            break
        
        else:
            print("\n❌ Неверный выбор. Пожалуйста, выберите число от 1 до 4.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")
        print("👋 До свидания!")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {str(e)}")
        import traceback
        traceback.print_exc()

