from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='driver')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    driver = db.relationship('Driver', back_populates='user', uselist=False)

    def __repr__(self):
        return f"<User {self.username} role={self.role}>"

    def set_password(self, raw_password: str):
        self.password = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        """Проверка пароля с поддержкой как хэшей, так и простого текста из seed-скрипта."""

        if not self.password:
            return False

        # Современный Werkzeug по умолчанию использует scrypt ("scrypt:"), а старые
        # версии — PBKDF2 ("pbkdf2:"), при этом в seed-скрипте пароли могут быть
        # сохранены в открытом виде. Поэтому пытаемся определить формат и проверить
        # корректно.
        if self.password.startswith(('pbkdf2:', 'scrypt:')):
            return check_password_hash(self.password, raw_password)

        # Фоллбек для простых текстовых паролей из первоначального заполнения БД.
        return self.password == raw_password
