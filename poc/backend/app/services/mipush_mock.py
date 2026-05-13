"""In-memory MiPush mock backend — used in tests and local dev."""

from __future__ import annotations


class MockMiPushClient:
    def __init__(self) -> None:
        self.sent_messages: list[dict] = []

    async def send_to_user(
        self,
        reg_id: str,
        payload: dict,
        title: str,
        description: str,
    ) -> None:
        self.sent_messages.append(
            {
                "reg_id": reg_id,
                "payload": payload,
                "title": title,
                "description": description,
            }
        )

    def reset(self) -> None:
        self.sent_messages.clear()
