#pragma once

#include "G4UserRunAction.hh"
#include "PrimaryGeneration.hh"
#include "HistoManager.hh"
#include "DEConstruction.hh"
#include "HistoManager.hh"
#include "PrimaryGeneration.hh"
#include <G4ProcessType.hh>
#include <G4Types.hh>
#include <G4UserRunAction.hh>

#include "G4RunManager.hh"
#include "G4AccumulableManager.hh"
class RunAction : public G4UserRunAction {

public:
  RunAction(PrimaryGeneration*,HistoManager*);
  virtual ~RunAction();
  // 主函数
  virtual void BeginOfRunAction(const G4Run *run);
  virtual void EndOfRunAction(const G4Run *run);

// 接口
public:
  PrimaryGeneration* GetPrimaryGenerator() const { return fPrimary; }
  HistoManager* GetHistoManager() const { return fHistoManager; }

  void AddEdep(G4double energy){fRunEdep+=energy;}


private:
  PrimaryGeneration* fPrimary;
  HistoManager* fHistoManager;

  G4bool Get_Thread_Status();

  G4Accumulable<G4double> fRunEdep;
  
};