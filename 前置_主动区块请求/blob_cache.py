import base64
import binascii
import time
from threading import Condition, RLock

from tooldelta import GameCtrl
from tooldelta.constants.packets import PacketIDS
from tooldelta.internal.launch_cli.neo_libs.blob_hash.packet.define import (
    HashWithPosition,
)


class PacketBlobHashClient:
    """通过标准 Minecraft 数据包获取缺失的 Blob 数据。"""

    def __init__(self, holder: "PacketBlobHashHolder") -> None:
        self._holder = holder

    def get_hash_payload(
        self, hashes: list[HashWithPosition]
    ) -> dict[HashWithPosition, bytes]:
        return self._holder.get_hash_payload(hashes)


class PacketBlobHashHolder:
    """不依赖接入点私有 API 的 Blob 缓存实现。"""

    def __init__(self, game_ctrl: GameCtrl, wait_timeout: float = 2.0) -> None:
        self._game_ctrl = game_ctrl
        self._wait_timeout = wait_timeout
        self._cache: dict[int, bytes] = {}
        self._lock = RLock()
        self._updated = Condition(self._lock)
        self._client = PacketBlobHashClient(self)

    @staticmethod
    def _decode_payload(value: object) -> bytes:
        if isinstance(value, str):
            try:
                return base64.b64decode(value, validate=True)
            except (binascii.Error, ValueError):
                return b""
        if isinstance(value, list):
            return bytes(value)
        if isinstance(value, (bytes, bytearray)):
            return bytes(value)
        return b""

    def on_cache_miss_response(self, packet: dict) -> bool:
        """接收 ClientCacheMissResponse 并唤醒等待中的区块处理线程。"""
        blobs = packet.get("Blobs")
        if not isinstance(blobs, list):
            return False
        with self._updated:
            for blob in blobs:
                if not isinstance(blob, dict):
                    continue
                try:
                    hash_value = int(blob["Hash"])
                except (KeyError, TypeError, ValueError):
                    continue
                payload = self._decode_payload(blob.get("Payload"))
                if payload:
                    self._cache[hash_value] = payload
            self._updated.notify_all()
        return False

    def load_blob_cache(self, hash_value: int) -> bytes:
        with self._lock:
            return self._cache.get(hash_value, b"")

    def update_blob_cache(self, hash_value: int, payload: bytes) -> bool:
        with self._updated:
            self._cache[hash_value] = bytes(payload)
            self._updated.notify_all()
        return True

    def get_client_function(self) -> PacketBlobHashClient:
        return self._client

    def get_hash_payload(
        self, hashes: list[HashWithPosition]
    ) -> dict[HashWithPosition, bytes]:
        requested = list(dict.fromkeys(item.hash for item in hashes))
        with self._lock:
            missing = [value for value in requested if value not in self._cache]
        if missing:
            self._game_ctrl.sendPacket(
                PacketIDS.IDClientCacheBlobStatus,
                {"MissHashes": missing, "HitHashes": []},
            )
            deadline = time.monotonic() + self._wait_timeout
            with self._updated:
                while any(value not in self._cache for value in missing):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    self._updated.wait(remaining)

        result: dict[HashWithPosition, bytes] = {}
        with self._lock:
            for item in hashes:
                payload = self._cache.get(item.hash)
                if payload is not None:
                    result[item] = payload
        return result
