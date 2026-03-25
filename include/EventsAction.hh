#pragma once
#include "G4IonTable.hh"
#include "HistoManager.hh"
#include <G4Types.hh>
#include <G4UserEventAction.hh>

class EventsAction : public G4UserEventAction {
public:
  explicit EventsAction(HistoManager *);
  virtual ~EventsAction();

  virtual void BeginOfEventAction(const G4Event *) override;
  virtual void EndOfEventAction(const G4Event *) override;


  // 接口
 public: 
  void AddEdep(G4double energy);
  HistoManager* GetHistoManager()const{return fHistoManager;}



private:
  HistoManager *fHistoManager;
  G4double fEventEdep;
};