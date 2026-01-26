from abc import ABC, abstractmethod


class RPCMethods(ABC):

    @abstractmethod
    def parameters(self):
        pass

    @abstractmethod
    def bestBlock(self):
        pass

    @abstractmethod
    def serviceData(self):
        pass

    @abstractmethod
    def subscribeServiceData(self):
        pass

    @abstractmethod
    def subscribeExportSegments(self):
        pass

    @abstractmethod
    def listServices(self, block_hash: bytes):
        pass
    #
    # @abstractmethod
    # def subscribeServicePreimage(self):
    #     pass
