def classFactory(iface):
    from .plugin import AIGisPlugin
    return AIGisPlugin(iface)
