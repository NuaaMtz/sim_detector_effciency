#include "SteppingAction.hh"
#include "RunAction.hh"
#include <G4Step.hh>
#include <G4UserSteppingAction.hh>

SteppingAction::SteppingAction(RunAction *runaction, EventsAction *eventaction)
    : G4UserSteppingAction(), frunAction(runaction), feventAction(eventaction) {}

SteppingAction::~SteppingAction() {}

void SteppingAction::UserSteppingAction(const G4Step *step) {

  // 获取能量沉积
  G4double edep = step->GetTotalEnergyDeposit();
  if (edep == 0) {
    return;
  }

  // 获取当前步的逻辑体
  auto preStepPoint = step->GetPreStepPoint();
  auto current_logicalVolume =
      preStepPoint->GetTouchableHandle()->GetVolume()->GetLogicalVolume();

  // 获取探测器逻辑体
  auto logical_sd_NaI=frunAction->GetPrimaryGenerator()->GetDetector()->GetLogicalSDNaI();
  
  // 是否在内
  if(logical_sd_NaI!=current_logicalVolume){
    return;
  }


  
  // 在EventAction中累积，EndOfEventAction统一写入一次
  feventAction->AddEdep(edep);
  feventAction->GetHistoManager()->FillStepsDeposite(edep);

}
