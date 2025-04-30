from contextlib import contextmanager
from datetime import date, timedelta
import json
from math import ceil
from pathlib import Path
import random
from typing import List
from typing import Literal
import uuid

from faker import Faker
from rich import print
from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, UUID, create_engine
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, sessionmaker

# Configuration
DATABASE_URI = "sqlite:///db.sqlite3"
FAKE_CLIENTS_COUNT = 100
LOANS_PER_CLIENT = (3, 10)
CLIENT_HAS_VENDOR_DATA_PROBABILITY = 0.6
FAKE_VENDOR_TRANSACTIONS_PER_CLIENT = (5, 30)


# Create a new declarative base instance
Base = declarative_base()

# Initialize Faker
fake = Faker(locale="en_US")


@contextmanager
def db_session(db_url: str):
    """
    Context manager to handle database connection and session lifecycle.
    """
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


class Client(Base):
    """
    Client model representing a client in the database.
    """

    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, unique=True)
    first_name: Mapped[str] = mapped_column(String(50))
    last_name: Mapped[str] = mapped_column(String(50))
    phone_number: Mapped[str] = mapped_column(String(20), unique=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)

    def __repr__(self):
        return f"<Client(id={self.id}, first_name={self.first_name}, last_name={self.last_name})>"


class Loan(Base):
    """
    Loan model representing a loan in the database.
    """

    __tablename__ = "loans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, unique=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    payment_amount: Mapped[float] = mapped_column(Numeric(10, 2))
    term: Mapped[int] = mapped_column(Integer)
    start_date: Mapped[date] = mapped_column(Date)

    def __repr__(self):
        return f"<Loan(id={self.id}, client_id={self.client_id}, amount={self.amount})>"


class CashFlow(Base):
    """
    CashFlow model representing a cash flow in the database.
    """

    __tablename__ = "cash_flows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, unique=True)
    loan_id: Mapped[int] = mapped_column(ForeignKey("loans.id"))
    type: Mapped[Literal["income", "expense"]] = mapped_column(String(10))
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    scheduled_date: Mapped[str] = mapped_column(Date)
    payment_date: Mapped[date] = mapped_column(Date)

    def __repr__(self):
        return f"<CashFlow(id={self.id}, loan_id={self.loan_id}, amount={self.amount})>"


class VendorTransaction(Base):
    """
    VendorTransaction model representing a vendor transaction in the database.
    """

    __tablename__ = "vendor_transactions"

    id: Mapped[UUID[str]] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True
    )
    phone_number: Mapped[str] = mapped_column(String(20))
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    merchant: Mapped[str] = mapped_column(String(100))
    transaction_date: Mapped[date] = mapped_column(Date)

    def __repr__(self):
        return (
            f"<VendorTransaction(id={self.id}, client_id={self.client_id}, amount={self.amount})>"
        )


class FakeMerchants(Base):
    """
    FakeMerchants model representing a fake merchants categorizations in the database.
    """

    __tablename__ = "fake_merchants"

    id: Mapped[UUID[str]] = mapped_column(
        Integer, primary_key=True, autoincrement=True, unique=True
    )
    category: Mapped[str] = mapped_column(String(100))
    merchant: Mapped[str] = mapped_column(String(100))

    def __repr__(self):
        return (
            f"<FakeMerchants(id={self.id}, category={self.category}, merchant={self.merchant})>"
        )


def fake_client() -> Client:
    """
    Generate a fake client using Faker.
    """
    return Client(
        first_name=fake.first_name(),
        last_name=fake.last_name(),
        phone_number="".join(c for c in fake.phone_number() if c.isdigit())[-10:],
        email=fake.email(),
    )


def fake_loan(client: Client, closed_before: date) -> Loan:
    """
    Generate a fake loan using Faker.
    """
    term = random.randint(1, 6)
    rate = random.uniform(0.08, 0.15)

    amount = (random.randint(2000, 5000) * term) // 1000 * 1000
    payment_amount = ceil(amount * (1 + rate) / term)

    # Generate a random start date within the last 30 days
    start_date = closed_before - timedelta(days=(random.randint(1, 30))) - timedelta(days=30 * term)

    return Loan(
        client_id=client.id,
        amount=amount,
        payment_amount=payment_amount,
        term=term,
        start_date=start_date,
    )


def fake_cash_flow_by_loan(loan: Loan) -> List[CashFlow]:
    cash_flows: List[CashFlow] = []

    cash_flows.append(
        CashFlow(
            loan_id=loan.id,
            type="expense",
            amount=loan.amount,
            scheduled_date=loan.start_date,
            payment_date=loan.start_date,
        )
    )

    for i in range(1, loan.term + 1):
        cash_flows.append(
            CashFlow(
                loan_id=loan.id,
                type="income",
                amount=loan.payment_amount,
                scheduled_date=loan.start_date + timedelta(days=i * 30),
                payment_date=loan.start_date
                + timedelta(days=i * 30)
                + timedelta(days=random.randint(-7, 7) if random.random() < 0.1 else 0),
            )
        )
    return cash_flows


def fake_vendor_transactions(client: Client, quantity: int) -> List[VendorTransaction]:
    """
    Generate fake vendor transactions for a client using Faker.
    """
    transactions: List[VendorTransaction] = []

    is_masked_merchants = random.random() < 1 / 3

    fake_merchants_file = Path(__file__).parent / "fake_merchants.json"
    if not fake_merchants_file.exists():
        raise FileNotFoundError(f"Fake merchants file not found at {fake_merchants_file.resolve()}")
    fake_merchants = json.loads(fake_merchants_file.read_text(encoding="utf-8"))

    for _ in range(quantity):
        merchant_category = random.choice(list(fake_merchants.keys()))
        merchant = random.choice(fake_merchants[merchant_category]).upper()
        if is_masked_merchants:
            merchant = merchant[:2] + "*****" + merchant[-1]
        amount = random.uniform(100, 5000)
        transaction_date = date.today() - timedelta(days=random.randint(1, 30 * 24))

        transactions.append(
            VendorTransaction(
                phone_number=client.phone_number,
                amount=amount,
                merchant=merchant,
                transaction_date=transaction_date,
            )
        )

    return list(sorted(transactions, key=lambda x: x.transaction_date))


def fake_merchants_categorization() -> List[FakeMerchants]:
    """
    Append fake merchants categorizations.
    """
    fake_merchants: List[FakeMerchants] = []

    with open('fake_merchants.json', 'r') as file:
        file_data = json.loads(file.read())

    for category, merchants in dict(file_data).items():
        for merchant in merchants:
            fake_merchants.append(
                FakeMerchants(
                    category=category,
                    merchant=merchant
                )
            )

    return fake_merchants


if __name__ == "__main__":
    fake = Faker()

    with db_session(DATABASE_URI) as session:
        # Delete existing data
        Base.metadata.drop_all(session.bind, checkfirst=True)
        # Create the table
        Base.metadata.create_all(session.bind)

        # Generate fake data
        for _ in range(FAKE_CLIENTS_COUNT):
            session.add(fake_client())
        session.commit()

    loans: List[Loan] = []
    for client in session.query(Client).all():
        # Generate vendor transactions for each client
        if random.random() < CLIENT_HAS_VENDOR_DATA_PROBABILITY:
            transactions_count = random.randint(*FAKE_VENDOR_TRANSACTIONS_PER_CLIENT)
            transactions = fake_vendor_transactions(client, transactions_count)
            for transaction in transactions:
                session.add(transaction)
        session.commit()

        # Generate random loans
        loans_count = random.randint(*LOANS_PER_CLIENT)
        closed_before = date.today()
        for _ in range(loans_count):
            loan = fake_loan(client, closed_before)
            loans.append(loan)
            closed_before = loan.start_date
    loans.sort(key=lambda x: x.start_date)
    for loan in loans:
        session.add(loan)
    session.commit()

    # Generate cash flows for each loan
    cash_flows: List[CashFlow] = []
    for loan in loans:
        cash_flows.extend(fake_cash_flow_by_loan(loan))
    cash_flows.sort(key=lambda x: x.scheduled_date)
    for cash_flow in cash_flows:
        session.add(cash_flow)
    session.commit()

    fake_merchants: List[FakeMerchants] = fake_merchants_categorization()
    for fake_merchant in fake_merchants:
        session.add(fake_merchant)
    session.commit()

print("[bold green]Fake data generated successfully!:rocket-emoji:")
