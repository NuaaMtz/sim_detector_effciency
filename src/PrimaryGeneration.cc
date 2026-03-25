#include "PrimaryGeneration.hh"
#include <G4ParticleTable.hh>
 #include <G4IonTable.hh>
PrimaryGeneration::PrimaryGeneration(DEConstruction *detector)
    : G4VUserPrimaryGeneratorAction(), fdetector(detector),fSourceName("Co60") {
  this->n_particle = 1; // 一个事件一个粒子
  fParticleGun = new G4ParticleGun(this->n_particle);

  fParticleGun->SetParticlePosition(G4ThreeVector(0, 0, 0));
  fParticleGun->SetParticleMomentumDirection(G4ThreeVector(0, 0, 1));// 动能为0时无效
}

PrimaryGeneration::~PrimaryGeneration() {}

void PrimaryGeneration::GeneratePrimaries(G4Event *anEvent) {
  // 修改这里可以快速切换衰变源
  // 根据UImanager传递的源名称选择相应的源
  if (fSourceName == "Co60") {
    SetSourceCo60();
  } else if (fSourceName == "Cs137") {
    SetSourceCs137();
  } else if (fSourceName == "Na22") {
    SetSourceNa22();
  } else if (fSourceName == "Am241") {
    SetSourceAm241();
  } else if (fSourceName == "Mn54") {
    SetSourceMn54();
  } else {
    // 默认源
    SetSourceCo60();
  }

  // 生成初级顶点
  fParticleGun->GeneratePrimaryVertex(anEvent);
}

void PrimaryGeneration::SetSourceCo60() { SetIonSource(27, 60); }

void PrimaryGeneration::SetSourceCs137() { SetIonSource(55, 137); }

void PrimaryGeneration::SetSourceNa22() { SetIonSource(11, 22); }

void PrimaryGeneration::SetSourceAm241() { SetIonSource(95, 241); }

void PrimaryGeneration::SetSourceMn54() { SetIonSource(25, 54); }

void PrimaryGeneration::SetIonSource(G4int Z, G4int A) {
  G4double charge = 0. * eplus; // 中性原子核
  G4double energy = 0. * keV;   // 静止

  // 实例化指定 Z, A 和激发态能量（这里取基态）的核离子
 
  G4IonTable* ionTable = G4IonTable::GetIonTable();
  G4ParticleDefinition *ion = ionTable->GetIon(Z, A, energy);
  fParticleGun->SetParticleDefinition(ion);
  fParticleGun->SetParticleCharge(charge);
  fParticleGun->SetParticleEnergy(energy);
}