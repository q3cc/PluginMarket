from tooldelta import GameCtrl
from tooldelta.constants.packets import PacketIDS
from tooldelta.mc_bytes_packet.sub_chunk_request import SubChunkRequest


def _is_fateark(game_ctrl: GameCtrl) -> bool:
    return getattr(game_ctrl.launcher, "launch_type", "") == "FateArk"


def send_sub_chunk_request(game_ctrl: GameCtrl, packet: SubChunkRequest) -> None:
    """发送 SubChunkRequest，并为仅接收字典包的 FateArk 做结构转换。"""
    if _is_fateark(game_ctrl):
        game_ctrl.sendPacket(
            PacketIDS.IDSubChunkRequest,
            {
                "Dimension": packet.Dimension,
                "Position": [
                    packet.SubChunkPosX,
                    packet.SubChunkPosY,
                    packet.SubChunkPosZ,
                ],
                "Offsets": [list(offset) for offset in packet.Offsets],
            },
        )
        return
    game_ctrl.sendPacket(PacketIDS.IDSubChunkRequest, packet)
