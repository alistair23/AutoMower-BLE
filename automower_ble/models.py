"""
    A list of supported Automower models
"""

# Copyright: Alistair Francis <alistair@alistair23.me>

class ModelInformation:
    def __init__(self, name:str, is_husqvarna:bool = True):
        self.name = name
        self.is_husqvarna = is_husqvarna

MowerModels = dict(
    [
        ((19, 1),  ModelInformation("115H")),
        ((23, 1),  ModelInformation("305")),
        ((23, 2),  ModelInformation("310MarkII")),
        ((23, 3),  ModelInformation("315MarkII")),
        ((11, 0),  ModelInformation("310")),
        ((12, 0),  ModelInformation("315")),
        ((12, 1),  ModelInformation("315X")),
        ((12, 23), ModelInformation("315XLimitedEdition")),
        ((5, 0),   ModelInformation("420")),
        ((7, 0),   ModelInformation("430X")),
        ((7, 1),   ModelInformation("430XH")),
        ((15, 0),  ModelInformation("440")),
        ((8, 0),   ModelInformation("450X")),
        ((8, 1),   ModelInformation("450XH")),
        ((17, 0),  ModelInformation("520")),
        ((17, 1),  ModelInformation("520H")),
        ((16, 0),  ModelInformation("550")),
        ((16, 1),  ModelInformation("550H")),
        ((27, 1),  ModelInformation("LibertyPilotEPAC")),
        ((27, 2),  ModelInformation("LibertyPilotNA")),
        ((27, 3),  ModelInformation("LibertyPilotHiCut")),
        ((28, 1),  ModelInformation("405X")),
        ((28, 2),  ModelInformation("415X")),
        ((20, 0),  ModelInformation("435XAWD")),
        ((21, 0),  ModelInformation("535AWD")),
        ((26, 3),  ModelInformation("520EPOS")),
        ((26, 4),  ModelInformation("520HEPOS")),
        ((26, 1),  ModelInformation("550EPOS")),
        ((26, 2),  ModelInformation("550HEPOS")),
        ((40, 1),  ModelInformation("450XEPOS")),
        ((40, 2),  ModelInformation("450XHEPOS")),
        ((24, 2),  ModelInformation("Ceora544EPOS")),
        ((24, 1),  ModelInformation("Ceora546EPOS")),
        ((29, 2),  ModelInformation("Minimo", is_husqvarna=False)),
        ((31, 1),  ModelInformation("320Nera")),
        ((31, 2),  ModelInformation("430XNera")),
        ((31, 3),  ModelInformation("450XNera")),
        ((32, 1),  ModelInformation("AspireR4")),
        ((33, 1),  ModelInformation("430XEgalite")),
        ((39, 2),  ModelInformation("310ENera")),
        ((39, 5),  ModelInformation("410XENera")),
        ((0, 0),   ModelInformation("Unknown")),
    ]
)
