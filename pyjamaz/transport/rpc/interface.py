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
    def listServices(self):
        pass
    #
    # @abstractmethod
    # def subscribeServicePreimage(self):
    #     pass
