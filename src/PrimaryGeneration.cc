#include "PrimaryGeneration.hh"
#include <G4Electron.hh>
#include <G4Exception.hh>
#include <G4Gamma.hh>
#include <G4String.hh>
#include <G4ParticleTable.hh>
#include <G4IonTable.hh>
#include <Randomize.hh>
#include <chrono>
#include <cstdint>
#include <sstream>
#include <mutex>

#ifdef myROOTRUN
#include <TFile.h>
#include <TLeaf.h>
#include <TTree.h>
#endif

namespace {
#ifdef myROOTRUN
std::mutex gSpectrumCacheMutex;
G4bool gSpectrumCacheValid = false;
G4String gCachedRootFile;
G4String gCachedTreeName;
G4String gCachedBranchName;
G4double gCachedMinEnergy = 0.;
G4double gCachedMaxEnergy = 0.;
std::vector<G4double> gSpectrumEnergyCache;

void InvalidateSharedSpectrumCache() {
  std::lock_guard<std::mutex> lock(gSpectrumCacheMutex);
  gSpectrumCacheValid = false;
  gSpectrumEnergyCache.clear();
}
#endif
} // namespace
PrimaryGeneration::PrimaryGeneration(DEConstruction *detector)
    : G4VUserPrimaryGeneratorAction(), fdetector(detector),
      fSourceName("XrayTube"), fRandomMinEnergy(1.0 * MeV),
      fRandomMaxEnergy(7.5 * MeV), fSpectrumRootFile(""),
      fSpectrumTreeName("tree_save_steps_energy"), fSpectrumBranchName("energt"),
      fSpectrumMinEnergy(0.0 * keV), fSpectrumMaxEnergy(1.0e9 * keV),
      fSpectrumLoaded(false) {
  // 用当前时间初始化随机种子，避免每次程序启动都走同一随机序列。
  const auto now_ticks = std::chrono::high_resolution_clock::now().time_since_epoch().count();
  const auto mix = static_cast<unsigned long>(reinterpret_cast<std::uintptr_t>(this));
  const G4long seed = static_cast<G4long>(now_ticks ^ mix);
  G4Random::setTheSeed(seed);

  this->n_particle = 1; // 一个事件一个粒子
  fParticleGun = new G4ParticleGun(this->n_particle);

  fParticleGun->SetParticlePosition(G4ThreeVector(0, 0, 0));
  fParticleGun->SetParticleMomentumDirection(G4ThreeVector(0, 0, 1)); // 动能为0时无效
}

PrimaryGeneration::~PrimaryGeneration() {}

void PrimaryGeneration::GeneratePrimaries(G4Event *anEvent) {
  if (fSourceName == "XrayTube") {
    auto *electron = G4Electron::Definition();
    fParticleGun->SetParticleDefinition(electron);
    fParticleGun->SetParticleCharge(-1.0 * eplus);
    fParticleGun->SetParticlePosition(G4ThreeVector(0, 0, -5.0 * cm));
    fParticleGun->SetParticleMomentumDirection(G4ThreeVector(0, 0, 1));
    const G4double rnd = G4UniformRand();
    const G4double energy = fRandomMinEnergy + rnd * (fRandomMaxEnergy - fRandomMinEnergy);
    fParticleGun->SetParticleEnergy(energy);
    fParticleGun->GeneratePrimaryVertex(anEvent);
    return;
  }

  if (fSourceName == "RootSpectrum") {
    if (!fSpectrumLoaded) {
      LoadSpectrumFromRoot();
    }
    fParticleGun->SetParticleDefinition(G4Gamma::Definition());
    fParticleGun->SetParticleCharge(0.0);
    const G4double targetRadius =
        (fdetector != nullptr) ? fdetector->GetTargetRadius() : (1.0 * cm);
    G4ThreeVector samplePos;
    do {
      samplePos = G4ThreeVector((2.0 * G4UniformRand() - 1.0) * targetRadius,
                                (2.0 * G4UniformRand() - 1.0) * targetRadius,
                                (2.0 * G4UniformRand() - 1.0) * targetRadius);
    } while (samplePos.mag2() > targetRadius * targetRadius);
    fParticleGun->SetParticlePosition(samplePos);
    fParticleGun->SetParticleMomentumDirection(G4ThreeVector(0, 0, 1));
    fParticleGun->SetParticleEnergy(SampleSpectrumEnergy());
    fParticleGun->GeneratePrimaryVertex(anEvent);
    return;
  }

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

void PrimaryGeneration::SetSpectrumRootFile(const G4String &rootFile) {
  fSpectrumRootFile = rootFile;
  MarkSpectrumDirty();
}

void PrimaryGeneration::SetSpectrumTreeName(const G4String &treeName) {
  fSpectrumTreeName = treeName;
  MarkSpectrumDirty();
}

void PrimaryGeneration::SetSpectrumBranchName(const G4String &branchName) {
  fSpectrumBranchName = branchName;
  MarkSpectrumDirty();
}

void PrimaryGeneration::SetSpectrumMinEnergy(G4double minEnergy) {
  fSpectrumMinEnergy = minEnergy;
  MarkSpectrumDirty();
}

void PrimaryGeneration::SetSpectrumMaxEnergy(G4double maxEnergy) {
  fSpectrumMaxEnergy = maxEnergy;
  MarkSpectrumDirty();
}

void PrimaryGeneration::MarkSpectrumDirty() {
  fSpectrumLoaded = false;
  fSpectrumEnergies.clear();
#ifdef myROOTRUN
  InvalidateSharedSpectrumCache();
#endif
}

void PrimaryGeneration::LoadSpectrumFromRoot() {
#ifndef myROOTRUN
  G4Exception("PrimaryGeneration::LoadSpectrumFromRoot", "mydet/root-disabled",
              FatalException,
              "ROOT support is disabled. Reconfigure with USE_ROOT=ON.");
#else
  if (fSpectrumRootFile.empty() || fSpectrumTreeName.empty() ||
      fSpectrumBranchName.empty()) {
    G4Exception("PrimaryGeneration::LoadSpectrumFromRoot",
                "mydet/spectrum-config", FatalException,
                "RootSpectrum requires root file, tree and branch.");
  }
  if (fSpectrumMinEnergy > fSpectrumMaxEnergy) {
    G4Exception("PrimaryGeneration::LoadSpectrumFromRoot",
                "mydet/spectrum-range", FatalException,
                "Spectrum min energy is larger than max energy.");
  }

  // MT：多个 worker 同时用 TFile/TTree 会破坏 ROOT 与 G4Root 的初始化顺序。
  // 全进程只从磁盘读一次能谱，各线程复制缓存。
  std::lock_guard<std::mutex> lock(gSpectrumCacheMutex);
  if (gSpectrumCacheValid && gCachedRootFile == fSpectrumRootFile &&
      gCachedTreeName == fSpectrumTreeName &&
      gCachedBranchName == fSpectrumBranchName &&
      gCachedMinEnergy == fSpectrumMinEnergy &&
      gCachedMaxEnergy == fSpectrumMaxEnergy && !gSpectrumEnergyCache.empty()) {
    fSpectrumEnergies = gSpectrumEnergyCache;
    fSpectrumLoaded = true;
    return;
  }

  gSpectrumEnergyCache.clear();
  TFile inputFile(fSpectrumRootFile.c_str(), "READ");
  if (inputFile.IsZombie()) {
    G4Exception("PrimaryGeneration::LoadSpectrumFromRoot",
                "mydet/spectrum-open", FatalException,
                ("Cannot open ROOT file: " + fSpectrumRootFile).c_str());
  }

  TTree *tree = nullptr;
  inputFile.GetObject(fSpectrumTreeName.c_str(), tree);
  if (tree == nullptr) {
    G4Exception("PrimaryGeneration::LoadSpectrumFromRoot",
                "mydet/spectrum-tree", FatalException,
                ("Cannot find tree: " + fSpectrumTreeName).c_str());
  }

  TLeaf *leaf = tree->GetLeaf(fSpectrumBranchName.c_str());
  if (leaf == nullptr) {
    G4Exception("PrimaryGeneration::LoadSpectrumFromRoot",
                "mydet/spectrum-branch", FatalException,
                ("Cannot find branch/leaf: " + fSpectrumBranchName).c_str());
  }

  const auto nEntries = tree->GetEntries();
  gSpectrumEnergyCache.reserve(static_cast<std::size_t>(nEntries));
  for (Long64_t i = 0; i < nEntries; ++i) {
    tree->GetEntry(i);
    const G4double energy = leaf->GetValue();
    if (energy >= fSpectrumMinEnergy && energy <= fSpectrumMaxEnergy) {
      gSpectrumEnergyCache.push_back(energy);
    }
  }

  if (gSpectrumEnergyCache.empty()) {
    std::ostringstream oss;
    oss << "No spectrum entries left after filtering in [" << fSpectrumMinEnergy / keV
        << ", " << fSpectrumMaxEnergy / keV << "] keV.";
    G4Exception("PrimaryGeneration::LoadSpectrumFromRoot",
                "mydet/spectrum-empty", FatalException, oss.str().c_str());
  }

  gCachedRootFile = fSpectrumRootFile;
  gCachedTreeName = fSpectrumTreeName;
  gCachedBranchName = fSpectrumBranchName;
  gCachedMinEnergy = fSpectrumMinEnergy;
  gCachedMaxEnergy = fSpectrumMaxEnergy;
  gSpectrumCacheValid = true;

  fSpectrumEnergies = gSpectrumEnergyCache;
  fSpectrumLoaded = true;
#endif
}

G4double PrimaryGeneration::SampleSpectrumEnergy() const {
  if (fSpectrumEnergies.empty()) {
    G4Exception("PrimaryGeneration::SampleSpectrumEnergy",
                "mydet/spectrum-empty", FatalException,
                "Spectrum cache is empty.");
  }
  const auto n = static_cast<G4int>(fSpectrumEnergies.size());
  G4int idx = static_cast<G4int>(G4UniformRand() * n);
  if (idx >= n) {
    idx = n - 1;
  }
  return fSpectrumEnergies[idx];
}