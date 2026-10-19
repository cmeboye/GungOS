"""Geometry diagnostics remain distinct from unsupported kernel operations."""
class Issue(ValueError):
    def __init__(self,kind,message,step=None):
        self.kind=kind;self.detail=message;self.step=step
        names={'invalid':'Invalid','limit':'Limit','unsupported':'Unsupported',
               'precision':'Precision','non_manifold':'Non-manifold','calculation':'Calculation'}
        prefix=names[kind]+(' #%d'%step if step is not None else '')
        super().__init__(prefix+': '+message)
