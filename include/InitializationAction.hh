#pragma once

#include "DEConstruction.hh"
#include "G4VUserActionInitialization.hh"
#include <G4RunManager.hh>
#include "PrimaryGeneration.hh"
#include "HistoManager.hh"
class InitializationAction : public G4VUserActionInitialization {

public:
  // 析构和构造函数
  InitializationAction(DEConstruction *);
  virtual ~InitializationAction();

  // 主线程
  virtual void BuildForMaster() const override;
  // 工作线程
  virtual void Build() const override;
private:
    DEConstruction* fdetector;

};