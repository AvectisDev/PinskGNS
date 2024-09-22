import sys
from opcua import Client
from schedule import every, repeat, run_pending

sys.path.insert(0, "..")
RAILWAY = {
    'tank_weight': 0.0,
    'weight_is_stable': False,
}
AUTO = {
    'weight': 0.0,
    'weight_is_stable': False,
    'mass_total': 0.0,
    'volume_total': 0.0
}


def get_opc_value(addrstr):
    """
    Get value from OPC UA server by address:
    Can look it in Editor.exe(SimpleScada)->Variable-> Double-click on the necessary variable->address
    """

    var = client.get_node(addrstr)
    return var.get_value()


@repeat(every(5).seconds)
def get_opc_tags():
    global RAILWAY, AUTO

    try:
        client.connect()
        print('Connect to OPC server successful')

        RAILWAY['tank_weight'] = get_opc_value("ns=4; s=Address Space.PLC_SU1.railway_tank_weight")
        RAILWAY['weight_is_stable'] = get_opc_value("ns=4; s=Address Space.PLC_SU1.railway_tank_weight_is_stable")

        AUTO['weight'] = get_opc_value("ns=4; s=Address Space.PLC_SU2.auto_weight")
        AUTO['weight_is_stable'] = get_opc_value("ns=4; s=Address Space.PLC_SU2.weight_is_stable")
        AUTO['mass_total'] = get_opc_value("ns=4; s=Address Space.PLC_SU2.MicroMotion.Mass_total")
        AUTO['volume_total'] = get_opc_value("ns=4; s=Address Space.PLC_SU2.MicroMotion.Volume_total")

        client.disconnect()
        print('Disconnect from OPC server')

    except:
        print('no connection to OPC server')


if __name__ == "__main__":
    client = Client("opc.tcp://127.0.0.1:4841")

    while True:
        run_pending()
