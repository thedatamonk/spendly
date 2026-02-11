from datetime import datetime

from tinydb import TinyDB, Query

from app.models.schemas import Obligation, Transaction


class ObligationRepository:
    def __init__(self, db_path: str = "memory_ledger.json"):
        self.db = TinyDB(db_path)
        self.table = self.db.table("obligations")

    def add(self, obligation: Obligation) -> Obligation:
        data = obligation.model_dump(mode="json")
        data.pop("id", None)
        doc_id = self.table.insert(data)
        obligation.id = doc_id
        return obligation

    def get(self, id: int) -> Obligation | None:
        doc = self.table.get(doc_id=id)
        if doc is None:
            return None
        return Obligation(id=doc.doc_id, **doc)

    def get_by_person(self, name: str, status: str = "active") -> list[Obligation]:
        Ob = Query()
        docs = self.table.search(
            (Ob.person_name.test(lambda val: val.lower() == name.lower()))
            & (Ob.status == status)
        )
        return [Obligation(id=doc.doc_id, **doc) for doc in docs]

    def get_all(self, status: str | None = None) -> list[Obligation]:
        if status:
            Ob = Query()
            docs = self.table.search(Ob.status == status)
        else:
            docs = self.table.all()
        return [Obligation(id=doc.doc_id, **doc) for doc in docs]

    def update(self, id: int, **fields) -> Obligation | None:
        doc = self.table.get(doc_id=id)
        if doc is None:
            return None
        # Filter out None values so we only update provided fields
        updates = {k: v for k, v in fields.items() if v is not None}
        if updates:
            self.table.update(updates, doc_ids=[id])
        return self.get(id)

    def add_transaction(self, id: int, transaction: Transaction) -> Obligation | None:
        doc = self.table.get(doc_id=id)
        if doc is None:
            return None

        transactions = doc.get("transactions", [])
        transactions.append(transaction.model_dump(mode="json"))

        remaining = doc["remaining_amount"] - transaction.amount
        remaining = max(remaining, 0)

        updates = {
            "transactions": transactions,
            "remaining_amount": remaining,
        }
        if remaining == 0:
            updates["status"] = "settled"

        self.table.update(updates, doc_ids=[id])
        return self.get(id)

    def settle(self, id: int) -> Obligation | None:
        doc = self.table.get(doc_id=id)
        if doc is None:
            return None

        now = datetime.now().isoformat()
        remaining = doc["remaining_amount"]

        # Add a settlement transaction for the remaining amount if any
        transactions = doc.get("transactions", [])
        if remaining > 0:
            transactions.append(
                {"amount": remaining, "paid_at": now, "note": "Full settlement"}
            )

        self.table.update(
            {
                "status": "settled",
                "remaining_amount": 0,
                "transactions": transactions,
            },
            doc_ids=[id],
        )
        return self.get(id)

    def delete(self, id: int) -> bool:
        doc = self.table.get(doc_id=id)
        if doc is None:
            return False
        self.table.remove(doc_ids=[id])
        return True
