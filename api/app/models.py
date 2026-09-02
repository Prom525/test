
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from .db import Base
from datetime import datetime

class Machine(Base):
    __tablename__ = "machines"
    machine_id = Column(Integer, primary_key=True, index=True)
    type = Column(String(80), nullable=False)
    serienummer = Column(String(80), nullable=True)
    locatie = Column(String(120), nullable=True)
    installatiedatum = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=True)
    inspecties = relationship("Inspectie", back_populates="machine")

class Inspectie(Base):
    __tablename__ = "inspecties"
    inspectie_id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.machine_id"))
    datum = Column(DateTime, nullable=False, default=datetime.utcnow)
    verslag_text = Column(Text, nullable=True)
    score = Column(Integer, nullable=True)
    machine = relationship("Machine", back_populates="inspecties")
