#pragma once
// 实现同位素源
#include "DEConstruction.hh"
#include "G4ParticleGun.hh"
#include "G4SystemOfUnits.hh"
#include "G4VUserPrimaryGeneratorAction.hh"
#include <G4String.hh>
#include <G4Types.hh>
#include <vector>
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
  void SetSourceName(G4String newname){
    fSourceName=newname;
    if (fdetector) {
      fdetector->SetEnableTargetW(fSourceName == "XrayTube");
    }
  }
  G4String GetSourceName() const { return fSourceName; }
  G4bool IsXrayTubeMode() const { return fSourceName == "XrayTube"; }
  void SetSpectrumRootFile(const G4String &rootFile);
  void SetSpectrumTreeName(const G4String &treeName);
  void SetSpectrumBranchName(const G4String &branchName);
  void SetSpectrumMinEnergy(G4double minEnergy);
  void SetSpectrumMaxEnergy(G4double maxEnergy);
private:
  // 不同衰变源（每种源一个函数）
  void SetSourceCo60();
  void SetSourceCs137();
  void SetSourceNa22();
  void SetSourceAm241();
  void SetSourceMn54();
  void SetIonSource(G4int Z, G4int A);
  void MarkSpectrumDirty();
  void LoadSpectrumFromRoot();
  G4double SampleSpectrumEnergy() const;

private:
  G4int n_particle;
  G4ParticleGun *fParticleGun;
  DEConstruction *fdetector;
  G4String fSourceName;
  G4double fRandomMinEnergy;
  G4double fRandomMaxEnergy;
  G4String fSpectrumRootFile;
  G4String fSpectrumTreeName;
  G4String fSpectrumBranchName;
  G4double fSpectrumMinEnergy;
  G4double fSpectrumMaxEnergy;
  G4bool fSpectrumLoaded;
  std::vector<G4double> fSpectrumEnergies;
};