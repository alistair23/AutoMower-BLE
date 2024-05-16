"""
A list of supported Automower models
"""


# Copyright: Alistair Francis <alistair@alistair23.me>
class ModelInformation:
    def __init__(self, manufacturer: str, model: str):
        self.manufacturer = manufacturer
        self.model = model


MowerModels = dict(
    [
        ((0, 0), ModelInformation("Unknown", "Unknown (0,0)")),
        ((5, 0), ModelInformation("Husqvarna", "Automower 420")),
        ((7, 0), ModelInformation("Husqvarna", "Automower 430X")),
        ((7, 1), ModelInformation("Husqvarna", "Automower 430XH")),
        ((8, 0), ModelInformation("Husqvarna", "Automower 450X")),
        ((8, 1), ModelInformation("Husqvarna", "Automower 450XH")),
        ((11, 0), ModelInformation("Husqvarna", "Automower 310")),
        ((12, 0), ModelInformation("Husqvarna", "Automower 315")),
        ((12, 1), ModelInformation("Husqvarna", "Automower 315X")),
        ((12, 23), ModelInformation("Husqvarna", "Automower 315X Limited Edition")),
        ((14, 1), ModelInformation("Gardena", "SILENO City 250")),
        ((14, 2), ModelInformation("Gardena", "SILENO City Unknown (14,2)")),
        ((14, 3), ModelInformation("Gardena", "SILENO City Unknown (14,3)")),
        ((14, 4), ModelInformation("Gardena", "SILENO City Unknown (14,4)")),
        ((14, 5), ModelInformation("Gardena", "SILENO City Unknown (14,5)")),
        ((14, 6), ModelInformation("Gardena", "SILENO City 500")),
        ((14, 7), ModelInformation("Gardena", "Smart SILENO City Unknown (14,7)")),
        ((14, 8), ModelInformation("Gardena", "Smart SILENO City Unknown (14,8)")),
        ((14, 9), ModelInformation("Gardena", "SILENO City Unknown (14,9)")),
        ((14, 10), ModelInformation("Gardena", "SILENO City Unknown (14,10)")),
        ((14, 11), ModelInformation("Gardena", "SILENO City Unknown (14,11)")),
        ((14, 12), ModelInformation("Gardena", "Smart SILENO City Unknown (14,12)")),
        ((14, 13), ModelInformation("Gardena", "SILENO City Unknown (14,13)")),
        ((14, 14), ModelInformation("Gardena", "Smart SILENO City Unknown (14,14)")),
        ((14, 15), ModelInformation("Gardena", "Smart SILENO City Unknown (14,15)")),
        ((14, 16), ModelInformation("Gardena", "Smart SILENO City Unknown (14,16)")),
        ((14, 17), ModelInformation("Gardena", "Smart SILENO City Unknown (14,17)")),
        ((14, 18), ModelInformation("Gardena", "SILENO City Unknown (14,18)")),
        ((15, 0), ModelInformation("Husqvarna", "Automower 440")),
        ((16, 0), ModelInformation("Husqvarna", "Automower 550")),
        ((16, 1), ModelInformation("Husqvarna", "Automower 550H")),
        ((17, 0), ModelInformation("Husqvarna", "Automower 520")),
        ((17, 1), ModelInformation("Husqvarna", "Automower 520H")),
        ((18, 1), ModelInformation("Gardena", "SILENO Life Unknown (18,1)")),
        ((18, 2), ModelInformation("Gardena", "SILENO Life Unknown (18,2)")),
        ((18, 3), ModelInformation("Gardena", "SILENO Life Unknown (18,3)")),
        ((18, 4), ModelInformation("Gardena", "Smart SILENO Life Unknown (18,4)")),
        ((18, 5), ModelInformation("Gardena", "Smart SILENO Life Unknown (18,5)")),
        ((18, 6), ModelInformation("Gardena", "Smart SILENO Life Unknown (18,6)")),
        ((18, 7), ModelInformation("Gardena", "SILENO Life Unknown (18,7)")),
        ((18, 8), ModelInformation("Gardena", "SILENO Life Unknown (18,8)")),
        ((18, 9), ModelInformation("Gardena", "Smart SILENO Life Unknown (18,9)")),
        ((18, 10), ModelInformation("Gardena", "Smart SILENO Life Unknown (18,10)")),
        ((18, 11), ModelInformation("Gardena", "Smart SILENO Life Unknown (18,11)")),
        ((18, 12), ModelInformation("Gardena", "SILENO Life Unknown (18,12)")),
        ((18, 13), ModelInformation("Gardena", "SILENO Life Unknown (18,13)")),
        ((18, 14), ModelInformation("Gardena", "Smart SILENO Life Unknown (18,14)")),
        ((18, 15), ModelInformation("Gardena", "Smart SILENO Life Unknown (18,15)")),
        ((18, 16), ModelInformation("Gardena", "SILENO Life Unknown (18,16)")),
        ((18, 17), ModelInformation("Gardena", "Smart SILENO Life Unknown (18,17)")),
        ((19, 1), ModelInformation("Husqvarna", "Automower 115H")),
        ((20, 0), ModelInformation("Husqvarna", "Automower 435X AWD")),
        ((21, 0), ModelInformation("Husqvarna", "Automower 535 AWD")),
        ((22, 1), ModelInformation("McCulloch", "Rob Unknown (22,1)")),
        ((22, 2), ModelInformation("McCulloch", "Rob Unknown (22,2)")),
        ((22, 3), ModelInformation("McCulloch", "Rob Unknown (22,3)")),
        ((22, 4), ModelInformation("McCulloch", "Rob S800")),
        ((23, 1), ModelInformation("Husqvarna", "Automower 305")),
        ((23, 2), ModelInformation("Husqvarna", "Automower 310 Mark II")),
        ((23, 3), ModelInformation("Husqvarna", "Automower 315 Mark II")),
        ((24, 1), ModelInformation("Husqvarna", "Automower Ceora 546 EPOS")),
        ((24, 2), ModelInformation("Husqvarna", "Automower Ceora 544 EPOS")),
        ((25, 1), ModelInformation("Flymo", "Easilife Unknown (25,1)")),
        ((25, 2), ModelInformation("Flymo", "Easilife Unknown (25,2)")),
        ((25, 3), ModelInformation("Flymo", "Easilife Unknown (25,3)")),
        ((25, 4), ModelInformation("Flymo", "Easilife Unknown (25,4)")),
        ((26, 1), ModelInformation("Husqvarna", "Automower 550 EPOS")),
        ((26, 2), ModelInformation("Husqvarna", "Automower 550H EPOS")),
        ((26, 3), ModelInformation("Husqvarna", "Automower 520 EPOS")),
        ((26, 4), ModelInformation("Husqvarna", "Automower 520H EPOS")),
        ((27, 1), ModelInformation("Husqvarna", "Liberty Pilot EPAC")),
        ((27, 2), ModelInformation("Husqvarna", "Liberty Pilot NA")),
        ((27, 3), ModelInformation("Husqvarna", "Liberty Pilot HiCut")),
        ((28, 1), ModelInformation("Husqvarna", "Automower 405X")),
        ((28, 2), ModelInformation("Husqvarna", "Automower 415X")),
        ((29, 1), ModelInformation("Gardena", "SILENO Minimo Unknown (29,1)")),
        ((29, 2), ModelInformation("Gardena", "SILENO Minimo 400")),
        ((29, 3), ModelInformation("Gardena", "SILENO Minimo 500")),
        ((29, 4), ModelInformation("Gardena", "SILENO Minimo 250")),
        ((29, 5), ModelInformation("Gardena", "SILENO Minimo Unknown (29,5)")),
        ((29, 6), ModelInformation("Gardena", "SILENO Minimo Unknown (29,6)")),
        ((29, 7), ModelInformation("Gardena", "SILENO Minimo Unknown (29,7)")),
        ((29, 8), ModelInformation("Gardena", "SILENO Minimo Unknown (29,8)")),
        ((29, 9), ModelInformation("Gardena", "SILENO Minimo 350")),
        ((29, 10), ModelInformation("Gardena", "SILENO Minimo Unknown (29,10)")),
        ((30, 1), ModelInformation("Flymo", "Easilife Go Unknown (30,1)")),
        ((30, 2), ModelInformation("Flymo", "Easilife Go Unknown (30,2)")),
        ((30, 3), ModelInformation("Flymo", "Easilife Go Unknown (30,3)")),
        ((30, 4), ModelInformation("Flymo", "Easilife Go Unknown (30,4)")),
        ((30, 5), ModelInformation("Flymo", "Easilife Go 500")),
        ((31, 1), ModelInformation("Husqvarna", "Automower 320 Nera")),
        ((31, 2), ModelInformation("Husqvarna", "Automower 430X Nera")),
        ((31, 3), ModelInformation("Husqvarna", "Automower 450X Nera")),
        ((32, 1), ModelInformation("Husqvarna", "Automower Aspire R4")),
        ((33, 1), ModelInformation("Husqvarna", "Automower 430X Egalite")),
        ((39, 2), ModelInformation("Husqvarna", "Automower 310E Nera")),
        ((39, 5), ModelInformation("Husqvarna", "Automower 410XE Nera")),
        ((40, 1), ModelInformation("Husqvarna", "Automower 450X EPOS")),
        ((40, 2), ModelInformation("Husqvarna", "Automower 450XH EPOS")),
    ]
)
