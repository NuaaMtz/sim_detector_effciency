#include "RunAction.hh"
#include <G4Run.hh>
#include <G4Types.hh>

RunAction::RunAction(PrimaryGeneration *primary, HistoManager *histimanaegr)
    : G4UserRunAction(), fPrimary(primary), fHistoManager(histimanaegr),
      fRunEdep(0) {
  G4AccumulableManager *accumulableManager = G4AccumulableManager::Instance();
  accumulableManager->RegisterAccumulable(fRunEdep);
}

RunAction::~RunAction() {}

void RunAction::BeginOfRunAction(const G4Run *) {
  // 创建ROOT文件
  fHistoManager->Book();

  // run级别的数据保存
  // 判断当前是否在工作线程或者是单线程模式
  if (Get_Thread_Status()) {
  }
}

void RunAction::EndOfRunAction(const G4Run *run) {

  // 如果事件序号为0，则直接返回。因为此时没有任何事件被处理，
  // 无需进行后续的数据保存或统计等操作，避免无意义的空数据输出。
  if (run->GetNumberOfEvent() == 0) {
    return;
  }

  // run级别的数据保存也只在工作线程
  if (Get_Thread_Status()) {
  }

  // 保存
  fHistoManager->Save();
}

// 判断当前是否在工作线程或者是单线程模式
G4bool RunAction::Get_Thread_Status() {
  return G4Threading::IsWorkerThread() ||
         G4RunManager::GetRunManager()->GetRunManagerType() ==
             G4RunManager::RMType::sequentialRM;
}