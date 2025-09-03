from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class Alarm(SQLModel, table=True):
    __tablename__ = "alarms"
    id: Optional[int] = Field(default=None, primary_key=True)
    zone_id: int
    zone_name: str
    vrijeme: str
    korisnik: Optional[str]
    soba: Optional[str]
    potvrda: int
    osoblje: Optional[str]
    vrijemePotvrde: Optional[str]

class Osoblje(SQLModel, table=True):
    __tablename__ = "osoblje"
    id: Optional[int] = Field(default=None, primary_key=True)
    ime: str
    sifra: str
    aktivna: int

class Comm(SQLModel, table=True):
    __tablename__ = "comm"
    key: str = Field(primary_key=True)
    value: int

class Zone(SQLModel, table=True):
    __tablename__ = "zone"
    id: Optional[int] = Field(default=None, primary_key=True)
    naziv: str
    korisnik_id: Optional[int] = Field(default=None, foreign_key="korisnici.id")

class Korisnik(SQLModel, table=True):
    __tablename__ = "korisnici"
    id: Optional[int] = Field(default=None, primary_key=True)
    ime: str
    soba: Optional[str]
    

def create_db_and_tables(engine):
    SQLModel.metadata.create_all(engine)
