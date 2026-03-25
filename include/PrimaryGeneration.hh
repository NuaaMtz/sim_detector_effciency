#pragma once
// 实现同位素源
#include "DEConstruction.hh"
#include "G4ParticleGun.hh"
#include "G4SystemOfUnits.hh"
#include "G4VUserPrimaryGeneratorAction.hh"
#include <G4String.hh>
#include <G4Types.hh>
class PrimaryGeneration : public G4VUserPrimaryGeneratorAction {
public:
  PrimaryGeneration(DEConstruction *);
  virtual ~PrimaryGeneration();
  // 主函数
  virtual void GeneratePrimaries(G4Event *) override;

  // 接口函数
public:
  // 获取探测器指针的接口函数
  DEConstruction *GetDetector() const { return fdetector; }
  void SetSourceName(G4String newname){fSourceName=newname;}
private:
  // 不同衰变源（每种源一个函数）
  void SetSourceCo60();
  void SetSourceCs137();
  void SetSourceNa22();
  void SetSourceAm241();
  void SetSourceMn54();
  void SetIonSource(G4int Z, G4int A);

private:
  G4int n_particle;
  G4ParticleGun *fParticleGun;
  DEConstruction *fdetector;
  G4String fSourceName;
};