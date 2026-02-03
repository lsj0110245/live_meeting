from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Alembic Config 객체
# .ini 파일의 설정 값에 접근할 수 있게 해줍니다.
config = context.config

import os, sys
# 프로젝트 루트 경로를 PYTHONPATH에 추가하여 패키지를 인식할 수 있게 함
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Python 로깅 설정을 위한 config 파일 해석
# 기본적으로 로거를 설정합니다.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 마이그레이션 대상 메타데이터 설정 ('autogenerate' 지원)
# target_metadata = mymodel.Base.metadata
from app.db.base import Base

target_metadata = Base.metadata
# Alembic이 감지할 수 있도록 모델들을 import 합니다
from app.models import user, meeting, transcript, summary, intermediate_summary

# config에서 다른 값들을 가져올 수 있습니다:
# my_important_option = config.get_main_option("my_important_option")
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """오프라인 모드에서 마이그레이션 실행.

    Engine을 생성하지 않고 URL만으로 context를 구성합니다.
    DBAPI가 필요하지 않습니다.

    context.execute() 호출은 SQL 스크립트를 출력합니다.
    """
    import os
    url = os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """온라인 모드에서 마이그레이션 실행.

    Engine을 생성하고 context와 연결합니다.
    """
    configuration = config.get_section(config.config_ini_section, {})
    if os.getenv("DATABASE_URL"):
        configuration["sqlalchemy.url"] = os.getenv("DATABASE_URL")

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
