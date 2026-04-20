#include "SteppingAction.hh"
#include "RunAction.hh"
#include "XrayTrackInfo.hh"
#include <G4Electron.hh>
#include <G4Step.hh>
#include <G4Track.hh>
#include <G4UserSteppingAction.hh>
#include <G4VUserTrackInformation.hh>

namespace {
bool IsTaggedTrack(const G4Track *track) {
  auto *info = dynamic_cast<const XrayTrackInfo *>(track->GetUserInformation());
  return info && info->IsFromTaggedXray();
}

void TagTrack(const G4Track *track) {
  auto *mutableTrack = const_cast<G4Track *>(track);
  if (mutableTrack->GetUserInformation() != nullptr) {
    return;
  }
  mutableTrack->SetUserInformation(new XrayTrackInfo(true));
}
} // namespace

SteppingAction::SteppingAction(RunAction *runaction, EventsAction *eventaction)
    : G4UserSteppingAction(), frunAction(runaction), feventAction(eventaction) {}

SteppingAction::~SteppingAction() {}

void SteppingAction::UserSteppingAction(const G4Step *step) {
  auto *track = step->GetTrack();
  auto *primary = frunAction->GetPrimaryGenerator();
  auto *detector = primary->GetDetector();
  const bool isXrayTubeMode = primary->IsXrayTubeMode();
  auto *logicalTargetW = detector->GetLogicalTargetW();
  auto *logicalSdNaI = detector->GetLogicalSDNaI();

  auto *preStepPoint = step->GetPreStepPoint();
  auto *currentLogicalVolume =
      preStepPoint->GetTouchableHandle()->GetVolume()->GetLogicalVolume();

  if (isXrayTubeMode && logicalTargetW != nullptr) {
    // 规则1：在钨靶内由主电子产生的光子打上标记
    const bool isPrimaryElectronInTarget =
        (track->GetParticleDefinition() == G4Electron::Definition()) &&
        (track->GetParentID() == 0) && (currentLogicalVolume == logicalTargetW);
    auto *secondaries = step->GetSecondaryInCurrentStep();
    if (secondaries) {
      for (const auto *secondary : *secondaries) {
        const bool isGamma = secondary->GetParticleDefinition()->GetParticleName() == "gamma";
        if ((isPrimaryElectronInTarget && isGamma) || IsTaggedTrack(track)) {
          TagTrack(secondary);
        }
      }
    }
  }

  // 获取能量沉积
  G4double edep = step->GetTotalEnergyDeposit();
  if (edep <= 0.02* MeV) {
    return;
  }

  // 只记录NaI中的能量沉积
  if (logicalSdNaI != currentLogicalVolume) {
    return;
  }

  // // 只有 XrayTube 模式才按标记筛选；其他放射源保持原逻辑
  // if (isXrayTubeMode && !IsTaggedTrack(track)) {
  //   return;
  // }

  // 在EventAction中累积，EndOfEventAction统一写入一次
  feventAction->AddEdep(edep);
  feventAction->GetHistoManager()->FillStepsDeposite(edep);

}
