import grpc
import bankingsystem_pb2
import bankingsystem_pb2_grpc
from concurrent import futures
import multiprocessing
from google.protobuf.json_format import MessageToDict
import json
from BankingSystemUtility import log_msg, initializeLogging, parseInputFile, getProcessId, parseLocalArgs, \
    translateEntityToEnum
from time import sleep


class Branch(bankingsystem_pb2_grpc.TransactionServicer):

    def __init__(self, id, balance, branches):
        # unique ID of the Branch
        self.id = id
        # replica of the Branch's balance
        self.balance = balance
        # the list of process IDs of the branches
        self.branches = branches
        # the list of Client stubs to communicate with the branches
        self.stubList = list()
        # a list of received messages used for debugging purpose
        self.recvMsg = list()
        # iterate the processID of the branches

    def MsgDelivery(self, request, context):
        log_msg('request::' + json.dumps(MessageToDict(request)))
        responseList = list()
        for event in request.events:
            if bankingsystem_pb2.query == event.interface:
                # Mandatory sleep after query interface so the results can be propagated.
                sleep(3)
                responseList.append(self.query())
            elif bankingsystem_pb2.deposit == event.interface:
                depositResponse = self.deposit(event)
                responseList.append(depositResponse)
                self.propagateIfOperationSuccessful(depositResponse, event, bankingsystem_pb2.propagate_deposit)
            elif bankingsystem_pb2.withdraw == event.interface:
                withdrawRes = self.withdraw(event)
                responseList.append(withdrawRes)
                self.propagateIfOperationSuccessful(withdrawRes, event, bankingsystem_pb2.propagate_withdraw)
            elif bankingsystem_pb2.propagate_deposit == event.interface:
                responseList.append(self.handlePropagateDeposit(event))
            elif bankingsystem_pb2.propagate_withdraw == event.interface:
                responseList.append(self.handlePropagateWithdraw(event))
        bankResponse = bankingsystem_pb2.BankResponse(id=request.id, recv=responseList)
        log_msg('Response from Branch#{0}:{1}'.format(self.id, json.dumps(MessageToDict(bankResponse))))
        return bankResponse

    def query(self):
        log_msg('-----QUERY-------')
        res = {'interface': bankingsystem_pb2.query, 'result': bankingsystem_pb2.success, 'money': self.balance}
        return res

    def deposit(self, event):
        log_msg('-----DEPOSIT-------')
        if event.money > 0:
            self.balance += event.money
            opResult = bankingsystem_pb2.success
        else:
            log_msg('Deposit amount negative.Operation failed.')
            opResult = bankingsystem_pb2.failure

        return {'interface': bankingsystem_pb2.deposit, 'result': opResult}

    def withdraw(self, event):
        log_msg('-----WITHDRAW-------')
        if event.money < 0 or self.balance - event.money < 0:
            log_msg('Insufficient funds for Withdraw.Operation failed.')
            opResult = bankingsystem_pb2.failure
        else:
            self.balance -= event.money
            opResult = bankingsystem_pb2.success
        return {'interface': bankingsystem_pb2.withdraw, 'result': opResult}

    def propagateIfOperationSuccessful(self, operationResponse, event, propagateOperation):
        if operationResponse['result'] == bankingsystem_pb2.success:
            self.propagateEvent(propagateOperation, event.money)
        else:
            log_msg('{0} operation failed. No propagation required.'.format(event.interface))

    def handlePropagateDeposit(self, event):
        log_msg('-----Handling Propagated Deposit-------')
        self.balance += event.money
        return {'interface': bankingsystem_pb2.propagate_deposit, 'result': bankingsystem_pb2.success}

    def handlePropagateWithdraw(self, event):
        log_msg('-----Handling Propagated Withdraw-------')
        self.balance -= event.money
        return {'interface': bankingsystem_pb2.propagate_withdraw, 'result': bankingsystem_pb2.success}

    def propagateEvent(self, eventType, amount):
        log_msg(f'-----Propagating Event {eventType} for amount {amount}-------')

        for bid in self.branches:
            portId = getProcessId(bid)

            log_msg('Propagating to branch {0} on port {1}'.format(bid, portId))
            with grpc.insecure_channel(f'localhost:{str(portId)}') as channel:
                stub = bankingsystem_pb2_grpc.TransactionStub(channel)
                req = [{"id": bid, "interface": eventType, "money": amount}]
                response = stub.MsgDelivery(
                    bankingsystem_pb2.BankRequest(id=bid, type=bankingsystem_pb2.branch, events=req))
                log_msg('Response on propagation {0} from branch {1}'.format(json.dumps(MessageToDict(response)), bid))

    def __str__(self):
        return "BRANCH[id = {0}, balance = {1} , branches = {2}".format(self.id,
                                                                        self.balance,
                                                                        str(self.branches))


def extractBranchData(parsedData):
    branches = list()
    branchIds = list()
    for data in parsedData:
        log_msg(data)
        if bankingsystem_pb2.branch == translateEntityToEnum(data['type']):
            log_msg('its a branch with id : %s' % data['id'])
            branches.append(Branch(id=data['id'], balance=data['balance'], branches=None))
            branchIds.append(data['id'])

    for branch in branches:
        branch.branches = [id for id in branchIds if branch.id != id]
        log_msg(branch)

    return branches


def startBranch(branch):
    portNumber = getProcessId(branch.id)
    log_msg(
        'Starting Branch server for {0} with balance {1} on port {2}'.format(branch.id, branch.balance, portNumber))
    options = (('grpc.so_reuseport', 1),)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10), options=options)
    bankingsystem_pb2_grpc.add_TransactionServicer_to_server(branch, server)
    server.add_insecure_port('[::]:{0}'.format(portNumber))
    server.start()
    server.wait_for_termination()


if __name__ == '__main__':
    initializeLogging()
    inputFile = parseLocalArgs()
    branches = extractBranchData(parseInputFile(inputFile[0]))

    workers = []
    for branch in branches:
        # NOTE: It is imperative that the worker subprocesses be forked before
        # any gRPC servers start up. See
        # https://github.com/grpc/grpc/issues/16001 for more details.
        worker = multiprocessing.Process(target=startBranch,
                                         args=(branch,))
        worker.start()
        workers.append(worker)
    for worker in workers:
        worker.join()
