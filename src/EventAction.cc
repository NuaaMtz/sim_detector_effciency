#include "EventsAction.hh"
#include <Randomize.hh>
#include <G4Event.hh>
#include <G4RunManager.hh>
#include <G4SystemOfUnits.hh>
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>

EventsAction::EventsAction(HistoManager *histomanager)
    : G4UserEventAction(), fHistoManager(histomanager), fEventEdep(0.) {}

EventsAction::~EventsAction() {}

void EventsAction::BeginOfEventAction(const G4Event *) { fEventEdep = 0.; }

void EventsAction::EndOfEventAction(const G4Event *event) {
  const G4int eventId = event->GetEventID();
  if ((eventId + 1) % 100000 == 0) {
    const G4int totalEvents =
        G4RunManager::GetRunManager()->GetNumberOfEventsToBeProcessed();
    const G4double progress =
        (totalEvents > 0) ? (100.0 * (eventId + 1) / totalEvents) : 0.0;
    std::cout << std::fixed << std::setprecision(2)
              << "[Progress] processed events: " << (eventId + 1) << "/"
              << totalEvents << " (" << progress << "%)" << std::endl;
  }

  // 高斯展宽：假设NaI在1 MeV处分辨率(FWHM/E)约为7%，并按1/sqrt(E)缩放
  const G4double resolutionAt1MeV = 0.10;
  const G4double fwhmToSigma = 2.355;
  const G4double energyMeV = std::max(fEventEdep / MeV, 0.0);
  const G4double sigma = (resolutionAt1MeV / fwhmToSigma) * std::sqrt(energyMeV) * MeV;
  const G4double smearedEdep = std::max(G4RandGauss::shoot(fEventEdep, sigma), 0.0);

  if (fEventEdep <= 0.02 * MeV) {
    return;
  }

  fHistoManager->FillEventsDeposite(fEventEdep);

  // 模拟电子学低能截止：仅在event总沉积能量上做阈值判断
  // if (smearedEdep <= 0.02 * MeV) {
  //   return;
  // }
  // fHistoManager->FillEventsDeposite(smearedEdep);
}

void EventsAction::AddEdep(G4double energy) { fEventEdep += energy; }
