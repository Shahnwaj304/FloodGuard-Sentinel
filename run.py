import os
from app import create_app
app = create_app()

if __name__ == '__main__':
    app_env = os.getenv('APP_ENV', 'development').lower()
    app.run(debug=(app_env != 'production'))
