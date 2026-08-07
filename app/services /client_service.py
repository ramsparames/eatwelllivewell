from app.database import (
    create_client,
    get_client,
    get_clients,
)

def list_clients():
    return get_clients()

def get_client_profile(client_id):
    return get_client(client_id)

def add_client(
    name,
    email,
    phone,
    program,
):
    return create_client(
        name=name,
        email=email,
        phone=phone,
        program=program,
    )
